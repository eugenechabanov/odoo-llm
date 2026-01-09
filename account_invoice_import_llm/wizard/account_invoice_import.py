"""
OCA Invoice Import Wizard Integration

Integrates LLM-OCR extraction into OCA account_invoice_import wizard.
Overrides fallback_parse_pdf_invoice() to extract invoice data when
embedded XML parsers (UBL, Factur-X) fail.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class AccountInvoiceImport(models.TransientModel):
    _inherit = "account.invoice.import"

    @api.model
    def fallback_parse_pdf_invoice(self, file_data, company):
        """
        Fallback parser for PDFs without embedded XML.

        Called by parse_pdf_invoice() when no XML is found in PDF.
        Delegates to account.invoice.import.ocr AbstractModel for extraction.

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

        # Delegate to OCR extraction AbstractModel
        return self.env["account.invoice.import.ocr"].extract_invoice_data(
            file_data, company
        )
