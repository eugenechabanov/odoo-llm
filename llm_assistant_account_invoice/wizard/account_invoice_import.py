"""
OCA Invoice Import Wizard Integration

This module integrates LLM-OCR extraction into the OCA account_invoice_import wizard.

Flow when OCA account_invoice_import is installed:
1. User uploads PDF → create_document_from_attachment() (overridden by OCA)
2. OCA creates wizard → calls import_invoices()
3. Wizard calls parse_pdf_invoice()
4. parse_pdf_invoice() tries:
   a) pdf_get_xml_files() - extract embedded XML (UBL, Factur-X)
   b) fallback_parse_pdf_invoice() ← OUR INTEGRATION HERE
5. Wizard creates invoice from parsed data

We override fallback_parse_pdf_invoice() to use LLM-OCR extraction as a fallback
when other parsers fail.

Expected return format (Invoice Pivot Format):
{
    'type': 'in_invoice',  # or 'in_refund'
    'partner': {'vat': 'BE0123456789', 'name': 'Vendor Name', ...},
    'currency': {'iso': 'EUR'},
    'date': '2024-01-15',
    'date_due': '2024-02-14',
    'amount_untaxed': 100.0,
    'amount_total': 121.0,
    'invoice_number': 'INV-2024-001',
    'lines': [
        {
            'name': 'Product description',
            'qty': 1.0,
            'price_unit': 100.0,
            'taxes': [{'amount_type': 'percent', 'amount': 21.0}],
        }
    ],
    'chatter_msg': [],
}
"""

import base64
import logging

from odoo import _, api, models

_logger = logging.getLogger(__name__)


class AccountInvoiceImport(models.TransientModel):
    _inherit = "account.invoice.import"

    @api.model
    def fallback_parse_pdf_invoice(self, file_data, company):
        """
        Fallback parser for PDFs without embedded XML.

        Called by parse_pdf_invoice() when no XML is found in PDF.
        This is the extension point for adding custom PDF parsers.

        Args:
            file_data (bytes): Raw PDF file content
            company (res.company): Company context for parsing

        Returns:
            dict: Invoice pivot format, or False if parsing failed
        """
        # Call parent first (allows other modules to handle first)
        res = super().fallback_parse_pdf_invoice(file_data, company)

        if res:
            # Another module already handled it
            return res

        # Try our LLM-OCR extraction
        temp_attachment = None
        temp_invoice = None

        try:
            # Create temporary attachment from raw bytes
            # Attachment is passed via context, so no need to link it to invoice
            temp_attachment = self.env["ir.attachment"].create(
                {
                    "name": "temp_invoice_import.pdf",
                    "datas": base64.b64encode(file_data),
                    "mimetype": "application/pdf",
                }
            )

            # Create temporary invoice for thread context
            temp_invoice = self.env["account.move"].create(
                {
                    "move_type": "in_invoice",
                    "company_id": company.id,
                }
            )

            # Extract invoice data - attachment passed via context (no linking needed)
            invoice_data = temp_invoice._extract_invoice_data_from_attachment(
                temp_attachment
            )

            if not invoice_data:
                return False

            # Convert our extraction format → Invoice Pivot Format
            return self._convert_llm_data_to_pivot(invoice_data, company)

        except Exception as e:
            _logger.error(f"LLM-OCR extraction failed: {e}", exc_info=True)
            return False

        finally:
            # Clean up temporary records
            if temp_invoice and temp_invoice.exists():
                temp_invoice.unlink()
            if temp_attachment and temp_attachment.exists():
                temp_attachment.unlink()

    @api.model
    def _convert_llm_data_to_pivot(self, llm_data, _company):
        """
        Convert LLM extraction format → Invoice Pivot Format

        LLM Format (camelCase):
        {
            "vendorName": "Supplier Inc.",
            "vat": "BE0123456789",
            "invoiceNumber": "INV-2024-001",
            "invoiceDate": "2024-01-15",
            "dueDate": "2024-02-14",
            "currency": "EUR",
            "subtotalAmount": 100.0,
            "taxAmount": 21.0,
            "totalAmount": 121.0,
            "lines": [
                {
                    "description": "Product",
                    "quantity": 1.0,
                    "unitPrice": 100.0,
                    "taxPercent": 21.0
                }
            ]
        }

        Pivot Format (snake_case):
        {
            'type': 'in_invoice',
            'partner': {'vat': 'BE0123456789', 'name': 'Supplier Inc.'},
            'currency': {'iso': 'EUR'},
            'date': '2024-01-15',
            'date_due': '2024-02-14',
            'amount_untaxed': 100.0,
            'amount_total': 121.0,
            'invoice_number': 'INV-2024-001',
            'lines': [...],
            'chatter_msg': [],
        }
        """
        parsed_inv = {
            "type": "in_invoice",
            "chatter_msg": [],
        }

        # Partner info
        if llm_data.get("vendorName") or llm_data.get("vat"):
            partner_data = {}
            if llm_data.get("vendorName"):
                partner_data["name"] = llm_data["vendorName"]
            if llm_data.get("vat"):
                # Clean VAT: remove spaces and make uppercase
                vat = llm_data["vat"].replace(" ", "").upper()
                partner_data["vat"] = vat
            parsed_inv["partner"] = partner_data

        # Currency
        currency_code = llm_data.get("currency", "EUR")
        parsed_inv["currency"] = {"iso": currency_code}

        # Dates
        if llm_data.get("invoiceDate"):
            parsed_inv["date"] = llm_data["invoiceDate"]
        if llm_data.get("dueDate"):
            parsed_inv["date_due"] = llm_data["dueDate"]

        # Invoice number
        if llm_data.get("invoiceNumber"):
            parsed_inv["invoice_number"] = llm_data["invoiceNumber"]

        # Amounts
        if llm_data.get("subtotalAmount") is not None:
            parsed_inv["amount_untaxed"] = float(llm_data["subtotalAmount"])
        if llm_data.get("totalAmount") is not None:
            parsed_inv["amount_total"] = float(llm_data["totalAmount"])

        # Invoice lines
        if llm_data.get("lines"):
            pivot_lines = []
            for llm_line in llm_data["lines"]:
                pivot_line = {
                    "name": llm_line.get("description", "Invoice Line"),
                    "qty": float(llm_line.get("quantity", 1.0)),
                    "price_unit": float(llm_line.get("unitPrice", 0.0)),
                }

                # Tax info
                if llm_line.get("taxPercent") is not None:
                    tax_percent = float(llm_line["taxPercent"])
                    pivot_line["taxes"] = [
                        {
                            "amount_type": "percent",
                            "amount": tax_percent,
                            "unece_type_code": "VAT",
                        }
                    ]

                pivot_lines.append(pivot_line)

            parsed_inv["lines"] = pivot_lines
        else:
            # If no lines extracted, create a single line with total amount
            _logger.warning(
                "No invoice lines extracted by LLM, creating single line"
            )
            parsed_inv["lines"] = [
                {
                    "name": _("Invoice Line (no details extracted)"),
                    "qty": 1.0,
                    "price_unit": parsed_inv.get("amount_untaxed", 0.0),
                }
            ]

        # Add success message to chatter
        parsed_inv["chatter_msg"].append(
            _(
                "Invoice data extracted using LLM-OCR technology. "
                "Please verify the extracted information."
            )
        )

        return parsed_inv
