import json
import logging
import re
from lxml import etree

from odoo import api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    # ============================================================================
    # DECODER REGISTRATION (EDI Integration)
    # ============================================================================

    @api.model
    def _get_create_document_from_attachment_decoders(self):
        """Register LLM-OCR decoder at priority 15 (after EDI at priority 10)

        Priority chain:
        - 10: EDI (XML formats like UBL, CII, Factur-X) - Core Odoo
        - 15: Our LLM-OCR (PDFs with AI) - This module ✨
        - 20+: Future modules

        NOTE: Decoders are tried in order until one succeeds (returns truthy invoice).
        If EDI successfully processes an attachment with embedded XML, our decoder
        is never called! We only see attachments EDI couldn't handle.
        """
        res = super()._get_create_document_from_attachment_decoders()

        # Register our LLM-OCR decoder at priority 15
        res.append((15, self._llm_ocr_decoder_oneshot))

        return res

    @api.model
    def _llm_ocr_decoder_oneshot(self, attachment):
        """One-shot LLM-OCR decoder for invoice attachments

        This decoder is called automatically by Odoo when:
        1. User uploads attachment via journal "Upload" button
        2. User drags & drops attachment to existing invoice

        Flow:
        1. Check if suitable for OCR (PDF, image)
        2. Create draft invoice record for the thread
        3. Attach file to invoice (makes it findable by thread.get_context())
        4. Create thread with assistant (computes OCR in context)
        5. Call thread.generate(None) - auto-triggers with OCR text
        6. Extract JSON from assistant response
        7. Convert JSON to UBL XML
        8. Delegate to EDI for invoice population

        Args:
            attachment (ir.attachment): Invoice attachment to process

        Returns:
            account.move: Created invoice (or empty recordset if failed)
        """
        try:
            # 1. Check if we should process this attachment
            if not self._should_process_with_llm_ocr(attachment):
                _logger.info(
                    f"Skipping attachment {attachment.name} - not suitable for LLM-OCR"
                )
                return self.env["account.move"]  # Return empty, try next decoder

            _logger.info(
                f"LLM-OCR decoder processing attachment: {attachment.name} "
                f"(mimetype: {attachment.mimetype})"
            )

            # 2. Create draft invoice for the thread to attach to
            invoice = self.create(
                {
                    "move_type": "in_invoice",
                    "state": "draft",
                }
            )

            # 3. Attach the file to invoice (makes it findable by thread.get_context())
            attachment.write({"res_model": "account.move", "res_id": invoice.id})

            # 4. Get or create thread with assistant
            assistant = self.env["llm.assistant"].get_assistant_by_code(
                "invoice_extraction"
            )
            if not assistant:
                _logger.error("Invoice extraction assistant not configured")
                invoice.unlink()
                return self.env["account.move"]

            thread = self.env["llm.thread"].create(
                {
                    "name": f"Invoice Extraction - {attachment.name}",
                    "assistant_id": assistant.id,
                    "model_id": assistant.model_id.id,
                    "model": "account.move",
                    "res_id": invoice.id,
                }
            )

            # 5. Call generate() - auto-triggers with OCR computed in context
            _logger.info(
                f"Starting LLM extraction for invoice {invoice.id} with thread {thread.id}"
            )
            invoice_data = None
            for response_event in thread.generate(user_message_body=None):
                if response_event.get("type") == "message_create":
                    message = response_event.get("message", {})
                    if message.get("author_id"):  # Assistant message
                        body = message.get("body", "")
                        invoice_data = self._parse_invoice_json(body)
                        break  # ONE response only!

            # 6. Convert JSON to UBL XML and delegate to EDI
            if invoice_data:
                success = self._apply_extracted_data_via_edi(invoice, invoice_data)
                if success:
                    _logger.info(
                        f"Successfully created invoice {invoice.name or invoice.id} "
                        f"from {attachment.name}"
                    )
                    return invoice
                else:
                    _logger.warning(
                        f"LLM extraction succeeded but EDI processing failed for {attachment.name}"
                    )
                    invoice.unlink()
                    return self.env["account.move"]
            else:
                _logger.warning(
                    f"LLM extraction failed for attachment {attachment.name}"
                )
                invoice.unlink()
                return self.env["account.move"]

        except Exception as e:
            _logger.error(f"Error in LLM-OCR decoder: {str(e)}", exc_info=True)
            return self.env["account.move"]  # Return empty, try next decoder

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

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
        """Parse JSON from LLM response, handling markdown code blocks

        Args:
            response_text (str): LLM response text

        Returns:
            dict: Parsed invoice data, or None if parsing failed
        """
        # Extract JSON from markdown code blocks if present
        json_match = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL
        )
        if json_match:
            json_text = json_match.group(1)
        else:
            json_text = response_text.strip()

        try:
            return json.loads(json_text)
        except json.JSONDecodeError as e:
            _logger.error(
                f"Failed to parse LLM response as JSON: {response_text[:500]}"
            )
            return None

    # ============================================================================
    # JSON → UBL XML CONVERSION
    # ============================================================================

    def _apply_extracted_data_via_edi(self, invoice, invoice_data):
        """Apply extracted invoice data via EDI (converts JSON → UBL XML → EDI)

        This is the bridge between LLM extraction and EDI processing:
        1. Build UBL 2.0 XML tree from JSON
        2. Create temporary XML attachment
        3. Delegate to EDI's _update_invoice_from_attachment()

        Args:
            invoice (account.move): Draft invoice to populate
            invoice_data (dict): LLM-extracted invoice data

        Returns:
            bool: True if successful
        """
        try:
            # 1. Build UBL XML tree from extracted data
            ubl_tree = self._build_ubl_from_invoice_data(invoice_data)

            # 2. Convert tree to string
            ubl_xml = etree.tostring(
                ubl_tree, pretty_print=True, xml_declaration=True, encoding="UTF-8"
            )

            # 3. Create temporary XML attachment
            temp_attachment = self.env["ir.attachment"].create(
                {
                    "name": "llm_extracted_invoice.xml",
                    "datas": ubl_xml,
                    "res_model": "account.move",
                    "res_id": invoice.id,
                    "mimetype": "application/xml",
                }
            )

            # 4. Delegate to EDI for processing
            edi_format = self.env["account.edi.format"].search([], limit=1)
            if not edi_format:
                _logger.error("No EDI format found for processing UBL XML")
                return False

            result = edi_format._update_invoice_from_attachment(
                temp_attachment, invoice
            )

            # 5. Clean up temporary attachment
            temp_attachment.unlink()

            return bool(result)

        except Exception as e:
            _logger.error(f"Error applying extracted data via EDI: {str(e)}")
            return False

    def _build_ubl_from_invoice_data(self, invoice_data):
        """Build minimal UBL 2.0 XML tree from extracted invoice data

        Uses paths from UBL_XML_PATHS_REFERENCE.md to ensure Odoo can import correctly.

        Args:
            invoice_data (dict): Extracted invoice data from LLM with structure:
                {
                    "vendor_name": str,
                    "vat": str (optional),
                    "invoice_number": str,
                    "invoice_date": str (YYYY-MM-DD),
                    "due_date": str (YYYY-MM-DD, optional),
                    "currency": str (optional, default EUR),
                    "total_amount": float,
                    "lines": [
                        {
                            "description": str,
                            "quantity": float,
                            "unit_price": float,
                            "tax_percent": float (optional)
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

        # Invoice Number (REQUIRED)
        # Path: ./{*}ID
        etree.SubElement(root, f"{{{ns['cbc']}}}ID").text = invoice_data.get(
            "invoice_number", ""
        )

        # Invoice Date (REQUIRED)
        # Path: ./{*}IssueDate
        etree.SubElement(root, f"{{{ns['cbc']}}}IssueDate").text = invoice_data.get(
            "invoice_date", ""
        )

        # Due Date (OPTIONAL)
        # Path: ./{*}DueDate
        if invoice_data.get("due_date"):
            etree.SubElement(root, f"{{{ns['cbc']}}}DueDate").text = invoice_data[
                "due_date"
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
            "vendor_name", ""
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

        # ========================================================================
        # INVOICE LINES
        # ========================================================================

        lines = invoice_data.get("lines", [])
        total_tax = 0.0
        total_untaxed = 0.0

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
            # Formula: quantity × unit_price
            unit_price = line_data.get("unit_price", 0.0)
            line_total = quantity * unit_price
            total_untaxed += line_total

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

            # Tax Category (OPTIONAL but helpful)
            # Path: .//{ *}Item/{*}ClassifiedTaxCategory/{*}Percent
            tax_percent = line_data.get("tax_percent", 0.0)
            if tax_percent:
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

                # Calculate tax for this line
                line_tax = line_total * (tax_percent / 100)
                total_tax += line_tax

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
        # Use total_amount from LLM if available, otherwise calculated total
        final_total = invoice_data.get("total_amount", total_with_tax)
        payable.text = f"{final_total:.2f}"

        return root
