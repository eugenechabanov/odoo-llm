# Copyright 2025 Apexive Solutions LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

import logging
from typing import Any

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class LLMToolInvoiceExecutor(models.Model):
    """
    Invoice executor tool - applies approved analysis to invoice.

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
            ("invoice_executor", "Invoice Executor (Apply Analysis)")
        ]

    def invoice_executor_execute(
        self, invoice_id: int, approved_analysis: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Apply approved invoice analysis to create/update invoice.

        This is the "write" phase that modifies the database after the
        analyzer has gathered context and the user has approved.

        Parameters:
            invoice_id: ID of the account.move record
            approved_analysis: The analysis dict from invoice_analyzer,
                              possibly modified by user decisions

        Returns:
            Success summary or actionable error message

        Example LLM usage:
            analysis = invoice_analyzer(123)
            # User reviews and approves
            result = invoice_executor(123, analysis['suggested_invoice'])

            if result['status'] == 'success':
                # Tell user: "Invoice {result['invoice_number']} created!"
        """
        try:
            # Step 1: Validate invoice is editable
            invoice = self._validate_invoice_editable(invoice_id)

            # Step 2: Prepare line data (convert to Odoo format)
            line_vals_list = []
            for line_data in approved_analysis.get("lines", []):
                try:
                    line_vals = self._prepare_line_vals(invoice, line_data)
                    line_vals_list.append(line_vals)
                except Exception as e:
                    return self._error_response(
                        invoice,
                        f"Error preparing line '{line_data.get('description', '')}': {str(e)}",
                        failed_at="line_preparation",
                    )

            if not line_vals_list:
                return self._error_response(
                    invoice,
                    "No lines to create. Analysis must contain 'lines' array.",
                    failed_at="validation",
                )

            # Step 3: Execute database operations (atomic)
            try:
                # Clear existing lines
                if invoice.invoice_line_ids:
                    invoice.invoice_line_ids.unlink()

                # Create all lines in batch
                new_lines = self.env["account.move.line"].with_context(
                    check_move_validity=False
                ).create(line_vals_list)

                # Update header
                header_vals = self._prepare_header_vals(approved_analysis)
                if header_vals:
                    invoice.write(header_vals)

                # Trigger Odoo computations
                invoice.invalidate_recordset(
                    ["amount_untaxed", "amount_tax", "amount_total"]
                )

            except Exception as e:
                _logger.error(f"Error executing invoice updates: {e}", exc_info=True)
                return self._error_response(
                    invoice, str(e), failed_at="database_write"
                )

            # Step 4: Validate result
            validation = self._validate_result(invoice, approved_analysis)

            if not validation["success"]:
                return {
                    "status": "validation_warning",
                    "invoice_number": invoice.name,
                    "invoice_id": invoice.id,
                    "partner": invoice.partner_id.name,
                    "lines_created": len(new_lines),
                    "warnings": validation["errors"],
                    "totals": {
                        "subtotal": invoice.amount_untaxed,
                        "tax": invoice.amount_tax,
                        "total": invoice.amount_total,
                    },
                    "message": f"Invoice {invoice.name} created with {len(validation['errors'])} warnings",
                }

            # Step 5: Return success summary
            return {
                "status": "success",
                "invoice_number": invoice.name,
                "invoice_id": invoice.id,
                "partner": invoice.partner_id.name,
                "lines_created": len(new_lines),
                "totals": {
                    "subtotal": invoice.amount_untaxed,
                    "tax": invoice.amount_tax,
                    "total": invoice.amount_total,
                },
                "validation": {
                    "totals_match": validation.get("totals_match", True),
                    "expected_total": approved_analysis.get("totals", {}).get(
                        "expected_total", 0.0
                    ),
                    "actual_total": invoice.amount_total,
                },
                "message": f"✓ Invoice {invoice.name} created successfully with {len(new_lines)} lines",
            }

        except UserError as e:
            return self._error_response(None, str(e), failed_at="validation")
        except Exception as e:
            _logger.error(f"Invoice executor unexpected error: {e}", exc_info=True)
            return self._error_response(None, str(e), failed_at="unexpected")

    # ═══════════════════════════════════════════════════════════════
    # VALIDATION
    # ═══════════════════════════════════════════════════════════════

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
            "display_type": False,
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
            # No product, no account - try to get default
            account = self._get_default_account(invoice)
            if account:
                vals["account_id"] = account.id
            else:
                raise UserError(
                    _("Line '%s': account required when no product specified")
                    % line_data.get("description", "")
                )

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
        """Get default expense/income account based on invoice type"""
        if invoice.move_type in ("in_invoice", "in_refund"):
            # Vendor bill - expense account
            # Try to get from company
            account = self.env["account.account"].search(
                [
                    ("account_type", "=", "expense"),
                    ("company_id", "=", invoice.company_id.id),
                    ("deprecated", "=", False),
                ],
                limit=1,
            )
        else:
            # Customer invoice - income account
            account = self.env["account.account"].search(
                [
                    ("account_type", "=", "income"),
                    ("company_id", "=", invoice.company_id.id),
                    ("deprecated", "=", False),
                ],
                limit=1,
            )

        return account

    def _prepare_header_vals(self, approved_analysis: dict) -> dict:
        """Prepare invoice header fields from analysis"""
        vals = {}

        if approved_analysis.get("partner_id"):
            vals["partner_id"] = approved_analysis["partner_id"]

        if approved_analysis.get("ref"):
            vals["ref"] = approved_analysis["ref"]

        if approved_analysis.get("invoice_date"):
            vals["invoice_date"] = approved_analysis["invoice_date"]

        if approved_analysis.get("invoice_date_due"):
            vals["invoice_date_due"] = approved_analysis["invoice_date_due"]

        if approved_analysis.get("invoice_payment_term_id"):
            vals["invoice_payment_term_id"] = approved_analysis[
                "invoice_payment_term_id"
            ]

        return vals

    # ═══════════════════════════════════════════════════════════════
    # VALIDATION
    # ═══════════════════════════════════════════════════════════════

    def _validate_result(self, invoice, approved_analysis: dict) -> dict:
        """
        Validate created invoice matches expectations.

        Returns:
            {
                'success': bool,
                'totals_match': bool,
                'errors': [list of issues]
            }
        """
        errors = []

        # Check totals match (allow 0.01 difference for rounding)
        expected_total = approved_analysis.get("totals", {}).get("expected_total", 0.0)
        actual_total = invoice.amount_total

        totals_match = abs(expected_total - actual_total) < 0.01 if expected_total else True

        if expected_total and not totals_match:
            errors.append(
                f"Total mismatch: expected {expected_total:.2f}, got {actual_total:.2f}"
            )

        # Check all lines have accounts
        lines_without_account = invoice.invoice_line_ids.filtered(
            lambda l: not l.account_id and not l.display_type
        )
        if lines_without_account:
            errors.append(f"{len(lines_without_account)} line(s) missing account")

        # Check partner exists
        if not invoice.partner_id:
            errors.append("Partner not set")

        return {
            "success": len(errors) == 0,
            "totals_match": totals_match,
            "errors": errors,
        }

    # ═══════════════════════════════════════════════════════════════
    # ERROR FORMATTING
    # ═══════════════════════════════════════════════════════════════

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
