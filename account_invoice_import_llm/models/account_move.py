import base64
import json
import logging
import re
from lxml import etree

from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    # ============================================================================
    # MANUAL TRIGGER ACTION
    # ============================================================================

    def action_process_with_llm(self):
        """Manually trigger LLM-OCR processing for this invoice

        This method allows users to manually process an invoice that has an attachment.
        Useful for:
        - Invoices created before the module was installed
        - Invoices where automatic processing was skipped
        - Re-processing invoices after attachment changes

        Returns:
            dict: Action result with notification
        """
        self.ensure_one()

        # Check if invoice is in valid state
        if self.state != "draft":
            raise UserError(
                "Can only process draft invoices. "
                "This invoice is already posted or cancelled."
            )

        # Find PDF or image attachment
        attachment = self.env["ir.attachment"].search(
            [
                ("res_model", "=", "account.move"),
                ("res_id", "=", self.id),
                (
                    "mimetype",
                    "in",
                    ["application/pdf", "image/png", "image/jpeg", "image/jpg"],
                ),
            ],
            limit=1,
        )

        if not attachment:
            raise UserError(
                "No PDF or image attachment found on this invoice. "
                "Please attach an invoice document first."
            )

        # Extract data from attachment
        invoice_data = self._extract_invoice_data_from_attachment(attachment)

        if not invoice_data:
            raise UserError(
                f"Failed to extract data from {attachment.name}. "
                "The document may be unreadable or in an unsupported format."
            )

        # Populate invoice with extracted data
        success = self._populate_invoice_from_data(invoice_data)

        if success:
            # Reload the form view to show populated data
            return {
                "type": "ir.actions.act_window",
                "res_model": "account.move",
                "res_id": self.id,
                "view_mode": "form",
                "view_type": "form",
                "target": "current",
            }
        else:
            raise UserError(
                f"Failed to populate invoice from extracted data. "
                "Please check the logs for details."
            )

    # ============================================================================
    # DECODER REGISTRATION (EDI Integration)
    # ============================================================================

    @api.model
    def _get_create_document_from_attachment_decoders(self):
        """Register LLM-OCR decoder at priority 15 (after EDI at priority 10)

        Priority chain:
        - 10: EDI (XML formats like UBL, CII, Factur-X) - Core Odoo
        - 15: Our LLM-OCR (PDFs with AI) - This module
        - 20+: Future modules

        NOTE: Decoders are tried in order until one succeeds (returns truthy invoice).
        If EDI successfully processes an attachment with embedded XML, our decoder
        is never called! We only see attachments EDI couldn't handle.
        """
        res = super()._get_create_document_from_attachment_decoders()
        res.append((15, self._llm_ocr_decoder))
        return res

    @api.model
    def _llm_ocr_decoder(self, attachment):
        """LLM-OCR decoder for invoice attachments (automatic)

        This decoder is called automatically by Odoo's decoder chain when:
        1. User uploads attachment via journal "Upload" button
        2. Email with attachment received (alias)

        The decoder creates a new invoice and populates it with extracted data.
        The journal handles attachment linking AFTER the decoder returns.

        Args:
            attachment (ir.attachment): Invoice attachment to process

        Returns:
            account.move: Created and populated invoice, or empty recordset if failed
        """
        try:
            # 1. Check if suitable for LLM-OCR processing
            if not self._should_process_with_llm_ocr(attachment):
                return self.env["account.move"]

            # 2. Find appropriate journal (reuse EDI logic)
            journal = self._get_journal_for_import("in_invoice")
            if not journal:
                return self.env["account.move"]

            # 3. Create draft invoice with journal
            invoice = self.create({
                "move_type": "in_invoice",
                "journal_id": journal.id,
            })

            # 4. Extract data from attachment (passes attachment via context)
            invoice_data = invoice._extract_invoice_data_from_attachment(attachment)

            if not invoice_data:
                invoice.unlink()
                return self.env["account.move"]

            # 5. Populate invoice with extracted data
            success = invoice._populate_invoice_from_data(invoice_data)

            if success:
                return invoice
            else:
                invoice.unlink()
                return self.env["account.move"]

        except Exception as e:
            _logger.error(f"Error in LLM-OCR decoder: {str(e)}", exc_info=True)
            return self.env["account.move"]

    # ============================================================================
    # CORE EXTRACTION METHODS (Reusable)
    # ============================================================================

    def _extract_invoice_data_from_attachment(self, attachment):
        """Extract structured invoice data from attachment using OCR + LLM

        This is the core extraction logic that:
        1. Creates a thread with the extraction assistant
        2. Passes attachment via context (for OCR lookup)
        3. Gets structured JSON from LLM in one shot
        4. Parses and validates the response

        Args:
            attachment (ir.attachment): Invoice attachment (PDF or image)

        Returns:
            dict: Structured invoice data with keys (camelCase):
                - vendorName (str)
                - vat (str, optional)
                - invoiceNumber (str)
                - invoiceDate (str, YYYY-MM-DD)
                - dueDate (str, optional, YYYY-MM-DD)
                - currency (str, optional, default EUR)
                - totalAmount (float)
                - lines (list of dict):
                    - description (str)
                    - quantity (float)
                    - unitPrice (float)
                    - taxPercent (float, optional)
            None: If extraction failed
        """
        # Get the extraction assistant
        assistant = self.env["llm.assistant"].get_assistant_by_code(
            "invoice_extraction"
        )
        if not assistant:
            _logger.error("Invoice extraction assistant not configured")
            return None

        # Create thread with attachment ID in context
        # This allows thread.get_context() to find the attachment without it being linked yet
        thread = self.env["llm.thread"].with_context(
            llm_invoice_attachment_id=attachment.id
        ).create({
            "name": f"Invoice Extraction - {attachment.name}",
            "assistant_id": assistant.id,
            "prompt_id": assistant.prompt_id.id,
            "provider_id": assistant.provider_id.id,
            "model_id": assistant.model_id.id,
            "model": "account.move",
            "res_id": self.id,
        })

        # Call generate() - prepend messages from prompt provide the user message
        # The prompt template includes the user message with {{ ocr_text }}
        for _ in thread.generate(user_message_body=""):
            pass

        # After streaming completes, get the latest assistant message from thread
        last_message = thread.get_latest_llm_message()
        if last_message and last_message.llm_role == "assistant":
            body = last_message.body
            invoice_data = self._parse_invoice_json(body)
            if invoice_data:
                return invoice_data

        return None

    def _populate_invoice_from_data(self, invoice_data):
        """Populate THIS invoice from extracted data via EDI

        This method:
        1. Converts extracted JSON to UBL 2.0 XML
        2. Creates a temporary XML attachment
        3. Delegates to EDI for invoice population (partner matching, etc.)
        4. Cleans up temporary attachment

        Args:
            invoice_data (dict): Structured invoice data from LLM

        Returns:
            bool: True if successful, False otherwise
        """
        # 1. Build UBL XML tree from extracted data
        ubl_tree = self._build_ubl_from_invoice_data(invoice_data)

        # 2. Convert tree to bytes
        ubl_xml_bytes = etree.tostring(
            ubl_tree, pretty_print=True, xml_declaration=True, encoding="UTF-8"
        )

        # 3. Base64 encode for Odoo attachment (datas field expects base64)
        ubl_xml_base64 = base64.b64encode(ubl_xml_bytes)

        # 4. Create temporary XML attachment
        temp_attachment = self.env["ir.attachment"].create(
            {
                "name": "llm_extracted_invoice.xml",
                "datas": ubl_xml_base64,
                "res_model": "account.move",
                "res_id": self.id,
                "mimetype": "application/xml",
            }
        )

        # 5. Delegate to EDI for processing - search ALL UBL/CII formats for auto-detection
        # The EDI will use UBLVersionID and other fields to auto-detect the correct builder
        edi_formats = self.env["account.edi.format"].search(
            [
                ("code", "in", [
                    "facturx_1_0_05", "ubl_bis3", "ubl_de", "nlcius_1",
                    "efff_1", "ubl_2_1", "ubl_a_nz", "ubl_sg"
                ])
            ]
        )
        if not edi_formats:
            _logger.error(
                "No UBL/CII EDI formats found. "
                "Ensure account_edi_ubl_cii module is installed."
            )
            temp_attachment.unlink()
            return False

        # Call on all formats - EDI will auto-detect based on UBLVersionID in XML
        result = edi_formats._update_invoice_from_attachment(temp_attachment, self)

        # Check if self was modified even though result is empty
        if not result and self.invoice_line_ids:
            result = self

        # 6. Clean up temporary attachment
        temp_attachment.unlink()

        if result:
            # 7. Apply fiscal position tax mapping (EDI doesn't do this!)
            #
            # ISSUE: EDI imports taxes by matching percentage from UBL XML, but does NOT
            # apply fiscal position mappings. It directly writes to database, bypassing
            # the @api.onchange handlers that normally trigger tax mapping in the UI.
            #
            # IMPACT: For intra-EU invoices, EDI finds domestic tax (e.g., "BTW 21%")
            # instead of reverse charge tax (e.g., "Inkopen import binnen EU hoog 21%"),
            # resulting in incorrect tax amounts (0.84 EUR instead of 0.00 EUR).
            #
            # SOLUTION: Manually call fiscal_position.map_tax() after EDI completes.
            # This applies the same business logic that UI onchange handlers apply,
            # mapping domestic taxes → reverse charge taxes for EU B2B transactions.
            if self.fiscal_position_id:
                for line in self.invoice_line_ids:
                    if line.tax_ids:
                        original_taxes = line.tax_ids
                        mapped_taxes = self.fiscal_position_id.map_tax(original_taxes)
                        if mapped_taxes != original_taxes:
                            line.tax_ids = mapped_taxes

            return True
        else:
            return False

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    @api.model
    def _get_journal_for_import(self, move_type):
        """Find appropriate journal for invoice import (matches EDI logic)

        This method replicates the journal-finding logic used by EDI modules
        to ensure consistent behavior across import methods.

        Args:
            move_type (str): Invoice move type (e.g., 'in_invoice', 'out_invoice')

        Returns:
            account.journal: Found journal, or empty recordset if not found
        """
        # Check context for default journal first (like EDI does)
        journal = self.env["account.journal"].browse(
            self._context.get("default_journal_id")
        )
        if journal.exists():
            return journal

        # Determine journal type from move type
        if move_type in self.env["account.move"].get_purchase_types():
            journal_type = "purchase"
        elif move_type in self.env["account.move"].get_sale_types():
            journal_type = "sale"
        else:
            journal_type = "general"

        # Search for journal
        journal = self.env["account.journal"].search(
            [("company_id", "=", self.env.company.id), ("type", "=", journal_type)],
            limit=1,
        )

        if not journal:
            _logger.error(
                "No %s journal found for company %s",
                journal_type,
                self.env.company.name,
            )

        return journal

    def _should_process_with_llm_ocr(self, attachment):
        """Check if attachment is suitable for LLM-OCR processing

        NOTE: We don't need to check for embedded XML here!
        EDI decoder (priority 10) runs before us (priority 15).
        If EDI succeeds, our decoder never gets called.
        We only see attachments that EDI couldn't process.

        Args:
            attachment (ir.attachment): Attachment to check

        Returns:
            bool: True if suitable for LLM-OCR
        """
        # Only process PDFs and images
        if attachment.mimetype not in (
            "application/pdf",
            "image/png",
            "image/jpeg",
            "image/jpg",
        ):
            return False

        return True

    def _parse_invoice_json(self, response_text):
        """Parse JSON from LLM response, handling HTML and markdown code blocks

        Args:
            response_text (str): LLM response text (may be HTML)

        Returns:
            dict: Parsed invoice data, or None if parsing failed
        """
        # Convert HTML to plain text (removes <p>, <em>, etc.)
        # Note: Using camelCase field names so no underscores to worry about
        plain_text = html2plaintext(response_text).strip()

        # Extract JSON from markdown code blocks if present
        json_match = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```", plain_text, re.DOTALL
        )
        if json_match:
            json_text = json_match.group(1)
        else:
            json_text = plain_text

        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            _logger.error(
                f"Failed to parse LLM response as JSON: {response_text[:500]}"
            )
            return None

    # ============================================================================
    # JSON → UBL XML CONVERSION
    # ============================================================================

    def _build_ubl_from_invoice_data(self, invoice_data):
        """Build minimal UBL 2.0 XML tree from extracted invoice data

        Uses paths from UBL_XML_PATHS_REFERENCE.md to ensure Odoo can import correctly.

        Args:
            invoice_data (dict): Extracted invoice data from LLM with structure:
                {
                    "vendorName": str,
                    "vat": str (optional),
                    "invoiceNumber": str,
                    "invoiceDate": str (YYYY-MM-DD),
                    "dueDate": str (YYYY-MM-DD, optional),
                    "currency": str (optional, default EUR),
                    "totalAmount": float,
                    "lines": [
                        {
                            "description": str,
                            "quantity": float,
                            "unitPrice": float,
                            "taxPercent": float (optional)
                        }
                    ]
                }

        Returns:
            lxml.etree.Element: UBL XML tree
        """
        # Namespaces (UBL 2.0)
        ns = {
            None: "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
            "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
            "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        }

        # Create root element
        root = etree.Element(
            f"{{{ns[None]}}}Invoice",
            nsmap=ns,
        )

        # Currency (default EUR)
        currency = invoice_data.get("currency", "EUR")

        # ========================================================================
        # DOCUMENT LEVEL FIELDS
        # ========================================================================

        # UBL Version (REQUIRED for auto-detection by EDI)
        # Path: ./{*}UBLVersionID
        etree.SubElement(root, f"{{{ns['cbc']}}}UBLVersionID").text = "2.1"

        # Invoice Number (REQUIRED)
        # Path: ./{*}ID
        etree.SubElement(root, f"{{{ns['cbc']}}}ID").text = invoice_data.get(
            "invoiceNumber", ""
        )

        # Invoice Date (REQUIRED)
        # Path: ./{*}IssueDate
        etree.SubElement(root, f"{{{ns['cbc']}}}IssueDate").text = invoice_data.get(
            "invoiceDate", ""
        )

        # Due Date (OPTIONAL)
        # Path: ./{*}DueDate
        if invoice_data.get("dueDate"):
            etree.SubElement(root, f"{{{ns['cbc']}}}DueDate").text = invoice_data[
                "dueDate"
            ]

        # Document Currency (REQUIRED)
        # Path: ./{*}DocumentCurrencyCode
        etree.SubElement(root, f"{{{ns['cbc']}}}DocumentCurrencyCode").text = currency

        # ========================================================================
        # SUPPLIER PARTY (Vendor)
        # ========================================================================

        # Path: .//cac:AccountingSupplierParty/cac:Party
        supplier_party = etree.SubElement(
            root, f"{{{ns['cac']}}}AccountingSupplierParty"
        )
        party = etree.SubElement(supplier_party, f"{{{ns['cac']}}}Party")

        # Party Name (REQUIRED)
        # Path: .//cac:PartyName/cbc:Name
        party_name = etree.SubElement(party, f"{{{ns['cac']}}}PartyName")
        etree.SubElement(party_name, f"{{{ns['cbc']}}}Name").text = invoice_data.get(
            "vendorName", ""
        )

        # VAT (HIGHLY RECOMMENDED)
        # Path: .//cac:PartyTaxScheme/cbc:CompanyID
        if invoice_data.get("vat"):
            party_tax_scheme = etree.SubElement(
                party, f"{{{ns['cac']}}}PartyTaxScheme"
            )
            company_id = etree.SubElement(
                party_tax_scheme, f"{{{ns['cbc']}}}CompanyID"
            )
            company_id.text = invoice_data["vat"]

            # TaxScheme is REQUIRED for proper VAT identification
            tax_scheme = etree.SubElement(
                party_tax_scheme, f"{{{ns['cac']}}}TaxScheme"
            )
            etree.SubElement(tax_scheme, f"{{{ns['cbc']}}}ID").text = "VAT"

        # ========================================================================
        # INVOICE LINES
        # ========================================================================

        lines = invoice_data.get("lines", [])

        # Use extracted amounts from LLM (no calculations!)
        total_tax = invoice_data.get("taxAmount", 0.0)
        total_untaxed = invoice_data.get("subtotalAmount", 0.0)

        for idx, line_data in enumerate(lines, start=1):
            # Path: ./{*}InvoiceLine
            invoice_line = etree.SubElement(root, f"{{{ns['cac']}}}InvoiceLine")

            # Line ID (REQUIRED)
            # Path: ./cbc:ID
            etree.SubElement(invoice_line, f"{{{ns['cbc']}}}ID").text = str(idx)

            # Quantity (REQUIRED)
            # Path: ./{*}InvoicedQuantity
            quantity = line_data.get("quantity", 1.0)
            quantity_elem = etree.SubElement(
                invoice_line, f"{{{ns['cbc']}}}InvoicedQuantity"
            )
            quantity_elem.set("unitCode", "C62")  # C62 = items/units
            quantity_elem.text = str(quantity)

            # Line Total (REQUIRED)
            # Path: ./{*}LineExtensionAmount
            # Formula: quantity × unitPrice
            unit_price = line_data.get("unitPrice", 0.0)
            line_total = quantity * unit_price

            line_extension = etree.SubElement(
                invoice_line, f"{{{ns['cbc']}}}LineExtensionAmount"
            )
            line_extension.set("currencyID", currency)
            line_extension.text = f"{line_total:.2f}"

            # Item
            # Path: ./cac:Item
            item = etree.SubElement(invoice_line, f"{{{ns['cac']}}}Item")

            # Description (HIGHLY RECOMMENDED)
            # Path: ./{*}Item/{*}Description
            etree.SubElement(item, f"{{{ns['cbc']}}}Description").text = line_data.get(
                "description", ""
            )

            # Tax Category (REQUIRED for EDI tax matching)
            # Path: .//{ *}Item/{*}ClassifiedTaxCategory/{*}Percent
            # Always include, even if 0% (for reverse charge/exempt scenarios)
            tax_percent = line_data.get("taxPercent", 0.0)

            classified_tax = etree.SubElement(
                item, f"{{{ns['cac']}}}ClassifiedTaxCategory"
            )
            etree.SubElement(
                classified_tax, f"{{{ns['cbc']}}}Percent"
            ).text = f"{tax_percent:.2f}"

            tax_scheme = etree.SubElement(
                classified_tax, f"{{{ns['cac']}}}TaxScheme"
            )
            etree.SubElement(tax_scheme, f"{{{ns['cbc']}}}ID").text = "VAT"

            # Price
            # Path: ./{*}Price/{*}PriceAmount
            price = etree.SubElement(invoice_line, f"{{{ns['cac']}}}Price")
            price_amount = etree.SubElement(price, f"{{{ns['cbc']}}}PriceAmount")
            price_amount.set("currencyID", currency)
            price_amount.text = f"{unit_price:.2f}"

        # ========================================================================
        # TAX TOTAL
        # ========================================================================

        # Path: ./{*}TaxTotal/{*}TaxAmount
        tax_total_elem = etree.SubElement(root, f"{{{ns['cac']}}}TaxTotal")
        tax_amount = etree.SubElement(tax_total_elem, f"{{{ns['cbc']}}}TaxAmount")
        tax_amount.set("currencyID", currency)
        tax_amount.text = f"{total_tax:.2f}"

        # ========================================================================
        # LEGAL MONETARY TOTAL
        # ========================================================================

        # Path: ./{*}LegalMonetaryTotal
        legal_total = etree.SubElement(root, f"{{{ns['cac']}}}LegalMonetaryTotal")

        # Line Extension Amount (sum of all line totals)
        line_ext_total = etree.SubElement(
            legal_total, f"{{{ns['cbc']}}}LineExtensionAmount"
        )
        line_ext_total.set("currencyID", currency)
        line_ext_total.text = f"{total_untaxed:.2f}"

        # Tax Exclusive Amount
        # Path: ./{*}TaxExclusiveAmount
        tax_exclusive = etree.SubElement(
            legal_total, f"{{{ns['cbc']}}}TaxExclusiveAmount"
        )
        tax_exclusive.set("currencyID", currency)
        tax_exclusive.text = f"{total_untaxed:.2f}"

        # Tax Inclusive Amount
        # Path: ./{*}TaxInclusiveAmount
        total_with_tax = total_untaxed + total_tax
        tax_inclusive = etree.SubElement(
            legal_total, f"{{{ns['cbc']}}}TaxInclusiveAmount"
        )
        tax_inclusive.set("currencyID", currency)
        tax_inclusive.text = f"{total_with_tax:.2f}"

        # Payable Amount
        # Path: ./{*}PayableAmount
        payable = etree.SubElement(legal_total, f"{{{ns['cbc']}}}PayableAmount")
        payable.set("currencyID", currency)
        # Use totalAmount from LLM if available, otherwise calculated total
        final_total = invoice_data.get("totalAmount", total_with_tax)
        payable.text = f"{final_total:.2f}"

        return root
