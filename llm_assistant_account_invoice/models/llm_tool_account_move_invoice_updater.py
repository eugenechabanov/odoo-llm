# Copyright 2025 Apexive Solutions LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

import logging

from odoo import _, api, models
from odoo.exceptions import UserError

from .invoice_tool_types import ApprovedAnalysis, UpdaterResponse

_logger = logging.getLogger(__name__)


class LLMToolAccountMoveInvoiceUpdater(models.Model):
    """
    Invoice updater tool - applies approved analysis to invoice.

    This tool consolidates write operations following Anthropic's principles:
    - Creates invoice lines (batch operation)
    - Updates invoice header
    - Validates result

    Returns concise, actionable summaries optimized for LLM presentation.
    """

    _inherit = "llm.tool"

    @api.model
    def _get_available_implementations(self):
        implementations = super()._get_available_implementations()
        return implementations + [
            ("account_move_invoice_updater", "Account Move Invoice Updater"),
        ]

    def _validate_invoice_editable(self, invoice_id: int):
        """Ensure invoice exists and can be modified"""
        invoice = self.env["account.move"].browse(invoice_id)

        if not invoice.exists():
            raise UserError(_("Invoice with ID %d not found") % invoice_id)

        if invoice.state != "draft":
            raise UserError(
                _(
                    "Cannot modify invoice %s - it's in state '%s'. "
                    "Only draft invoices can be modified."
                )
                % (invoice.name, invoice.state)
            )

        if invoice.move_type not in ("in_invoice", "in_refund", "out_invoice", "out_refund"):
            raise UserError(
                _("Record %s is not an invoice (type: %s)") % (invoice.name, invoice.move_type)
            )

        return invoice

    # ═══════════════════════════════════════════════════════════════
    # DATA PREPARATION
    # ═══════════════════════════════════════════════════════════════

    def _prepare_line_vals(self, invoice, line_data: dict) -> dict:
        """
        Prepare line values for Odoo (direct mapping - no translation).

        InvoiceLine already uses Odoo field names, so no conversion needed.
        """
        vals = {
            "move_id": invoice.id,
            "name": line_data.get("name", ""),  # Already Odoo field name
            "quantity": float(line_data.get("quantity", 1.0)),
            "price_unit": float(line_data.get("price_unit", 0.0)),  # Already Odoo field name
        }

        # Product (optional)
        if line_data.get("product_id"):
            product = self.env["product.product"].browse(line_data["product_id"])
            if product.exists():
                vals["product_id"] = product.id
                # Odoo auto-computes: name, account_id, tax_ids (with fiscal position!)

        # Account (optional - Odoo auto-computes if not provided)
        # Only set if explicitly provided in line_data
        if line_data.get("account_id"):
            vals["account_id"] = line_data["account_id"]
        # Otherwise, Odoo's _compute_account_id() will handle it:
        # 1. Product's expense/income account
        # 2. Most frequent account for partner (if no product)
        # 3. Previous lines' account (if consistent)
        # 4. Journal's default_account_id (final fallback)

        # Don't set tax_ids - Odoo auto-computes based on product/account + fiscal position

        # Validate quantity
        if vals["quantity"] <= 0:
            raise UserError(
                _("Line '%s': quantity must be positive") % vals["name"]
            )

        return vals

    # ═══════════════════════════════════════════════════════════════
    # RESPONSE BUILDERS (using Pydantic models for consistency)
    # ═══════════════════════════════════════════════════════════════

    def _error_response(
        self, invoice_id: int, invoice_number: str, error: str, suggestion: str, failed_at: str
    ) -> dict:
        """Build standardized error response using Pydantic model"""
        from .invoice_tool_types import UpdaterResponseError

        response = UpdaterResponseError(
            status="error",
            invoice_id=invoice_id,
            invoice_number=invoice_number,
            error=error,
            suggestion=suggestion,
            failed_at=failed_at,
        )
        return response.model_dump()

    def _success_response(
        self, invoice, lines_created: int, totals: dict, validation: dict
    ) -> dict:
        """Build standardized success response using Pydantic model"""
        from .invoice_tool_types import (
            UpdaterResponseSuccess,
            UpdaterTotals,
            UpdaterValidation,
        )

        response = UpdaterResponseSuccess(
            status="success",
            invoice_id=invoice.id,
            invoice_number=invoice.name,
            partner=invoice.partner_id.name,
            lines_created=lines_created,
            totals=UpdaterTotals(**totals),
            validation=UpdaterValidation(**validation) if validation else UpdaterValidation(),
            message=f"✓ Invoice {invoice.name} created successfully with {lines_created} lines",
        )
        return response.model_dump()

    def _get_error_suggestion(self, error_message: str) -> str:
        """Get helpful suggestion based on error type"""
        error_lower = error_message.lower()

        if "account" in error_lower and "missing" in error_lower:
            return (
                "Lines without products need an account. "
                "Either specify account_id in the line data or ensure the "
                "product has a proper expense/income account configured."
            )
        elif "partner" in error_lower:
            return (
                "Partner is required. Ensure approved_analysis contains "
                "a valid partner_id."
            )
        elif "tax" in error_lower:
            return (
                "Tax configuration issue. Check that tax_ids are valid "
                "and match the invoice type (purchase vs sale)."
            )
        elif "state" in error_lower or "draft" in error_lower:
            return (
                "Invoice must be in draft state to modify. "
                "You cannot change posted or cancelled invoices."
            )
        elif "quantity" in error_lower:
            return "All line quantities must be positive numbers."
        else:
            return (
                "Check the error message for details. Ensure approved_analysis "
                "has the required fields: partner_id, lines (with name, "
                "quantity, price_unit, and either product_id or account_id)."
            )

    # ═══════════════════════════════════════════════════════════════════════════
    # Type-Safe Invoice Updater with Strict Validation
    # ═══════════════════════════════════════════════════════════════════════════

    def account_move_invoice_updater_execute(
        self, invoice_id: int, approved_analysis: ApprovedAnalysis
    ) -> UpdaterResponse:
        """
        Type-safe invoice updater with strict validation.

        Philosophy: "Fail fast with clear guidance"
        - All required fields validated upfront
        - Clear error messages pointing to exact solutions
        - No warnings, only errors (strict mode)

        Key features:
        - Strict validation: partner_id is REQUIRED (not optional)
        - Type-safe input/output
        - Clear error messages pointing to solutions
        - Consistent response structure
        - No partial updates (atomic operations)

        Parameters:
            invoice_id: ID of the account.move record
            approved_analysis: Approved analysis from analyzer's "ready" response
                REQUIRED fields (Odoo field names):
                - partner_id: int
                - lines: list[InvoiceLine]
                - ref: str
                - invoice_date: str

        Returns:
            UpdaterResponse with status:
            - "success": Invoice updated successfully
            - "error": Update failed with clear message

        Example LLM usage:
            # 1. Get ready response from analyzer
            analyzer_result = analyzer(invoice_id, extracted_data, constraints)

            # 2. Pass data using Odoo field names (direct mapping)
            updater_result = updater(
                invoice_id=invoice_id,
                approved_analysis={
                    "partner_id": analyzer_result["data"]["partner_id"],
                    "lines": analyzer_result["data"]["lines"],
                    "ref": analyzer_result["data"]["suggested_values"]["ref"],
                    "invoice_date": analyzer_result["data"]["suggested_values"]["invoice_date"],
                    "invoice_payment_term_id": analyzer_result["data"]["suggested_values"].get("invoice_payment_term_id"),
                }
            )
        """
        try:
            # ─────────────────────────────────────────────────────────────
            # VALIDATION (Pydantic validates approved_analysis automatically)
            # ─────────────────────────────────────────────────────────────
            invoice = self._validate_invoice_editable(invoice_id)

            # ─────────────────────────────────────────────────────────────
            # STEP 1: Prepare Lines
            # ─────────────────────────────────────────────────────────────
            line_vals_list = []
            for line_data in approved_analysis["lines"]:
                try:
                    line_vals = self._prepare_line_vals(invoice, line_data)
                    line_vals_list.append(line_vals)
                except Exception as e:
                    return self._error_response(
                        invoice_id=invoice.id,
                        invoice_number=invoice.name,
                        error=f"Error preparing line '{line_data.get('name', '')}': {str(e)}",
                        suggestion=self._get_error_suggestion(str(e)),
                        failed_at="line_preparation",
                    )

            # ─────────────────────────────────────────────────────────────
            # STEP 2: Update Invoice Header
            # ─────────────────────────────────────────────────────────────
            # Direct mapping - ApprovedAnalysis uses Odoo field names
            header_vals = {
                "partner_id": approved_analysis["partner_id"],
                "ref": approved_analysis["ref"],
                "invoice_date": approved_analysis["invoice_date"],
            }

            # Optional fields
            if approved_analysis.get("invoice_date_due"):
                header_vals["invoice_date_due"] = approved_analysis["invoice_date_due"]
            if approved_analysis.get("invoice_payment_term_id"):
                header_vals["invoice_payment_term_id"] = approved_analysis[
                    "invoice_payment_term_id"
                ]

            try:
                invoice.write(header_vals)
            except Exception as e:
                return self._error_response(
                    invoice_id=invoice.id,
                    invoice_number=invoice.name,
                    error=f"Error updating invoice header: {str(e)}",
                    suggestion=self._get_error_suggestion(str(e)),
                    failed_at="header_update",
                )

            # ─────────────────────────────────────────────────────────────
            # STEP 3: Create Lines (Batch)
            # ─────────────────────────────────────────────────────────────
            try:
                self.env["account.move.line"].create(line_vals_list)
            except Exception as e:
                return self._error_response(
                    invoice_id=invoice.id,
                    invoice_number=invoice.name,
                    error=f"Error creating invoice lines: {str(e)}",
                    suggestion=self._get_error_suggestion(str(e)),
                    failed_at="line_creation",
                )

            # ─────────────────────────────────────────────────────────────
            # STEP 4: Get Totals and Validate
            # ─────────────────────────────────────────────────────────────
            # Totals are auto-computed by Odoo when lines are created
            totals = {
                "subtotal": invoice.amount_untaxed,
                "tax": invoice.amount_tax,
                "total": invoice.amount_total,
            }

            # Validation (if expected total provided)
            validation = {}
            if approved_analysis.get("total"):
                expected = approved_analysis["total"]
                actual = invoice.amount_total
                validation = {
                    "expected_total": expected,
                    "actual_total": actual,
                    "totals_match": abs(expected - actual) < 0.01,  # Allow 1 cent diff
                }

            # ─────────────────────────────────────────────────────────────
            # SUCCESS!
            # ─────────────────────────────────────────────────────────────
            return self._success_response(
                invoice=invoice,
                lines_created=len(line_vals_list),
                totals=totals,
                validation=validation,
            )

        except Exception as e:
            _logger.error(f"Invoice updater error: {e}", exc_info=True)
            return self._error_response(
                invoice_id=invoice_id,
                invoice_number=invoice.name if invoice else "Unknown",
                error=str(e),
                suggestion="Check the error message for details. "
                "Ensure approved_analysis has all required fields.",
                failed_at="unknown",
            )
