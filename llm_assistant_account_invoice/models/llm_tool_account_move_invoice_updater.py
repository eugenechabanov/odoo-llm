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
            ("account_move_invoice_updater", "Account Move Invoice Updater (Type-Safe)"),
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
        Convert business-friendly line data → Odoo format.

        Handles all the Odoo-specific formatting that LLM doesn't need to know.
        """
        vals = {
            "move_id": invoice.id,
            "name": line_data.get("description", ""),
            "quantity": float(line_data.get("quantity", 1.0)),
            "price_unit": float(line_data.get("unit_price", 0.0)),
        }

        # Product (optional)
        if line_data.get("product_id"):
            product = self.env["product.product"].browse(line_data["product_id"])
            if product.exists():
                vals["product_id"] = product.id
                # Product auto-fills: name, account_id, tax_ids
                # But we can override them below

        # Account (required if no product)
        if line_data.get("account_id"):
            vals["account_id"] = line_data["account_id"]
        elif not line_data.get("product_id"):
            # No product, no account - try to get default from journal
            account = self._get_default_account(invoice)
            if account:
                vals["account_id"] = account.id
            # If no account found, let Odoo's own validation handle it

        # Taxes (convert to Odoo format)
        if "tax_ids" in line_data and line_data["tax_ids"]:
            # Analysis provides: [5, 12]
            # Odoo needs: [(6, 0, [5, 12])]
            vals["tax_ids"] = [(6, 0, line_data["tax_ids"])]

        # Validate quantity
        if vals["quantity"] <= 0:
            raise UserError(
                _("Line '%s': quantity must be positive") % vals["name"]
            )

        return vals

    def _get_default_account(self, invoice):
        """
        Get default account from journal (Odoo standard behavior).

        This follows Odoo's approach: use journal's default_account_id
        which is set per journal based on its type (purchase, sale, etc.)
        """
        # Use the journal's default account (Odoo standard)
        if invoice.journal_id and invoice.journal_id.default_account_id:
            return invoice.journal_id.default_account_id

        # Fallback: shouldn't happen with properly configured journals
        return None

    def _error_response(self, invoice, error_message: str, failed_at: str = None) -> dict:
        """
        Format errors in helpful, actionable way (Anthropic principle).

        Provides specific suggestions rather than cryptic error codes.
        """
        suggestion = self._get_error_suggestion(error_message)

        response = {
            "status": "error",
            "error": error_message,
            "suggestion": suggestion,
        }

        if failed_at:
            response["failed_at"] = failed_at

        if invoice:
            response["invoice_number"] = invoice.name
            response["invoice_id"] = invoice.id

        return response

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
                "has the required fields: partner_id, lines (with description, "
                "quantity, unit_price, and either product_id or account_id)."
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
                REQUIRED fields:
                - partner_id: int
                - lines: list[InvoiceLine]
                - ref: str
                - date: str

        Returns:
            UpdaterResponse with status:
            - "success": Invoice updated successfully
            - "error": Update failed with clear message

        Example LLM usage:
            # 1. Get ready response from analyzer
            analyzer_result = analyzer(invoice_id, extracted_data, constraints)

            # 2. Pass data.partner_id and data.lines to updater
            updater_result = updater(
                invoice_id=invoice_id,
                approved_analysis={
                    "partner_id": analyzer_result["data"]["partner_id"],
                    "lines": analyzer_result["data"]["lines"],
                    "ref": analyzer_result["data"]["suggested_values"]["ref"],
                    "date": analyzer_result["data"]["suggested_values"]["date"],
                    "payment_term_id": analyzer_result["data"]["suggested_values"].get("payment_term_id"),
                }
            )
        """
        try:
            # ─────────────────────────────────────────────────────────────
            # STRICT VALIDATION (Fail Fast!)
            # ─────────────────────────────────────────────────────────────
            invoice = self._validate_invoice_editable(invoice_id)

            # Validate REQUIRED partner_id
            if not approved_analysis.get("partner_id"):
                return {
                    "status": "error",
                    "invoice_id": invoice.id,
                    "invoice_number": invoice.name,
                    "error": "partner_id is REQUIRED in approved_analysis",
                    "suggestion": "Use the partner_id from analyzer's 'ready' response: "
                    "analyzer_result['data']['partner_id']",
                    "failed_at": "validation",
                }

            # Validate REQUIRED lines
            if not approved_analysis.get("lines"):
                return {
                    "status": "error",
                    "invoice_id": invoice.id,
                    "invoice_number": invoice.name,
                    "error": "lines array is REQUIRED in approved_analysis",
                    "suggestion": "Use the lines from analyzer's 'ready' response: "
                    "analyzer_result['data']['lines']",
                    "failed_at": "validation",
                }

            # Validate REQUIRED ref
            if not approved_analysis.get("ref"):
                return {
                    "status": "error",
                    "invoice_id": invoice.id,
                    "invoice_number": invoice.name,
                    "error": "ref (invoice reference) is REQUIRED",
                    "suggestion": "Use the ref from analyzer's 'suggested_values': "
                    "analyzer_result['data']['suggested_values']['ref']",
                    "failed_at": "validation",
                }

            # Validate REQUIRED date
            if not approved_analysis.get("date"):
                return {
                    "status": "error",
                    "invoice_id": invoice.id,
                    "invoice_number": invoice.name,
                    "error": "date (invoice date) is REQUIRED",
                    "suggestion": "Use the date from analyzer's 'suggested_values': "
                    "analyzer_result['data']['suggested_values']['date']",
                    "failed_at": "validation",
                }

            # ─────────────────────────────────────────────────────────────
            # STEP 1: Prepare Lines
            # ─────────────────────────────────────────────────────────────
            line_vals_list = []
            for line_data in approved_analysis["lines"]:
                try:
                    line_vals = self._prepare_line_vals(invoice, line_data)
                    line_vals_list.append(line_vals)
                except Exception as e:
                    return {
                        "status": "error",
                        "invoice_id": invoice.id,
                        "invoice_number": invoice.name,
                        "error": f"Error preparing line '{line_data.get('description', '')}': {str(e)}",
                        "suggestion": self._get_error_suggestion(str(e)),
                        "failed_at": "line_preparation",
                    }

            # ─────────────────────────────────────────────────────────────
            # STEP 2: Update Invoice Header
            # ─────────────────────────────────────────────────────────────
            header_vals = {
                "partner_id": approved_analysis["partner_id"],
                "ref": approved_analysis["ref"],
                "invoice_date": approved_analysis["date"],
            }

            # Optional fields
            if approved_analysis.get("due_date"):
                header_vals["invoice_date_due"] = approved_analysis["due_date"]
            if approved_analysis.get("payment_term_id"):
                header_vals["invoice_payment_term_id"] = approved_analysis[
                    "payment_term_id"
                ]

            try:
                invoice.write(header_vals)
            except Exception as e:
                return {
                    "status": "error",
                    "invoice_id": invoice.id,
                    "invoice_number": invoice.name,
                    "error": f"Error updating invoice header: {str(e)}",
                    "suggestion": self._get_error_suggestion(str(e)),
                    "failed_at": "header_update",
                }

            # ─────────────────────────────────────────────────────────────
            # STEP 3: Create Lines (Batch)
            # ─────────────────────────────────────────────────────────────
            try:
                self.env["account.move.line"].create(line_vals_list)
            except Exception as e:
                return {
                    "status": "error",
                    "invoice_id": invoice.id,
                    "invoice_number": invoice.name,
                    "error": f"Error creating invoice lines: {str(e)}",
                    "suggestion": self._get_error_suggestion(str(e)),
                    "failed_at": "line_creation",
                }

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
            return {
                "status": "success",
                "invoice_id": invoice.id,
                "invoice_number": invoice.name,
                "partner": invoice.partner_id.name,
                "lines_created": len(line_vals_list),
                "totals": totals,
                "validation": validation,
                "message": f"✓ Invoice {invoice.name} created successfully with {len(line_vals_list)} lines",
            }

        except Exception as e:
            _logger.error(f"Invoice updater error: {e}", exc_info=True)
            return {
                "status": "error",
                "invoice_id": invoice_id,
                "invoice_number": invoice.name if invoice else "Unknown",
                "error": str(e),
                "suggestion": "Check the error message for details. "
                "Ensure approved_analysis has all required fields.",
                "failed_at": "unknown",
            }
