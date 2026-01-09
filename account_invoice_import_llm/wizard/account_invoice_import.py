"""
OCA Invoice Import Wizard Integration

Integrates LLM-OCR extraction into OCA account_invoice_import wizard.
Overrides fallback_parse_pdf_invoice() to extract invoice data when
embedded XML parsers (UBL, Factur-X) fail.
"""

import json
import logging
import re

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountInvoiceImport(models.TransientModel):
    _inherit = "account.invoice.import"

    @api.model
    def fallback_parse_pdf_invoice(self, file_data, company):
        """
        Fallback parser for PDFs without embedded XML (Simplified - No temp records).

        Called by parse_pdf_invoice() when no XML is found in PDF.
        This is the extension point for adding custom PDF parsers.

        New simplified flow:
        1. Run OCR directly on file_data bytes
        2. Render prompt with OCR context (no thread)
        3. Call LLM directly (no thread)
        4. Parse response and convert to pivot format

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

        # Try our simplified LLM-OCR extraction (no temporary records)
        try:
            # Step 1: Run OCR directly on file bytes
            _logger.info("Running OCR on invoice file...")
            ocr_text = self._run_ocr_on_file_data(file_data)
            if not ocr_text:
                _logger.warning("OCR returned empty text")
                return False

            # Step 2: Render prompt with OCR context
            _logger.info("Rendering extraction prompt...")
            prepend_messages, assistant = self._render_invoice_extraction_prompt(
                ocr_text
            )

            # Step 3: Call LLM directly (no thread)
            _logger.info(
                f"Calling LLM for extraction (model: {assistant.model_id.name})..."
            )
            llm_response = self._call_llm_for_extraction(prepend_messages, assistant)

            # Step 4: Parse LLM response
            _logger.info("Parsing LLM response...")
            invoice_data = self._parse_llm_response(llm_response)
            if not invoice_data:
                _logger.warning("Failed to parse LLM response as JSON")
                return False

            # Step 5: Convert to pivot format
            _logger.info("Converting to Invoice Pivot Format...")
            pivot_data = self._convert_llm_data_to_pivot(invoice_data, company)

            _logger.info("LLM-OCR extraction completed successfully")
            return pivot_data

        except Exception as e:
            _logger.error(f"LLM-OCR extraction failed: {e}", exc_info=True)
            return False

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

        Note: OCA wizard automatically adds the original file to parsed_inv["attachments"]
        after the parser returns, so we don't need to include it here.
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

    # ============================================================================
    # SIMPLIFIED EXTRACTION METHODS (No temporary records)
    # ============================================================================

    @api.model
    def _run_ocr_on_file_data(self, file_data, mimetype="application/pdf"):
        """Run OCR directly on file bytes without creating attachment

        This method calls Mistral OCR provider directly without creating
        temporary attachment records. Uses the same OCR processing as
        llm_tool_ocr_mistral but without the attachment wrapper.

        Args:
            file_data (bytes): Raw file content
            mimetype (str): MIME type of the file

        Returns:
            str: Extracted OCR text in markdown format

        Raises:
            UserError: If Mistral provider or OCR model not configured
        """
        # Get Mistral provider
        provider = self.env["llm.provider"].search(
            [("service", "=", "mistral")], limit=1
        )
        if not provider:
            raise UserError(_(
                "Mistral provider not configured. "
                "Please configure Mistral AI provider in LLM settings."
            ))

        # Delegate to provider's method - single source of truth for OCR model selection
        ocr_model = provider.mistral_get_default_ocr_model()

        # Call provider's OCR processing directly
        ocr_response = provider.process_ocr(
            model_name=ocr_model.name,
            data=file_data,
            mimetype=mimetype,
        )

        # Format response to markdown (same as llm_tool_ocr_mistral)
        parts = []
        for page_idx, page in enumerate(ocr_response.pages, start=1):
            page_md = page.markdown.strip() if page.markdown else ""
            if page_md:
                parts.append(f"## Page {page_idx}\n\n{page_md}")

        return "\n\n".join(parts) if parts else ""

    @api.model
    def _render_invoice_extraction_prompt(self, ocr_text):
        """Render the invoice extraction prompt with OCR text

        This method uses the prompt's get_messages() method to render
        the template with OCR text context (no thread needed).

        Args:
            ocr_text (str): OCR extracted text from invoice

        Returns:
            tuple: (prepend_messages, assistant) ready for model.chat()

        Raises:
            UserError: If assistant or prompt not configured
        """
        # Get the invoice extraction assistant
        assistant = self.env["llm.assistant"].get_assistant_by_code(
            "invoice_extraction"
        )
        if not assistant or not assistant.prompt_id:
            raise UserError(_(
                "Invoice Extraction Assistant Not Found\n\n"
                "The invoice extraction assistant is required but not configured.\n\n"
                "Please check:\n"
                "1. Go to Settings → LLM → Assistants\n"
                "2. Ensure 'Invoice Extraction' assistant exists\n"
                "3. Code should be: invoice_extraction\n"
                "4. Ensure it has a prompt configured"
            ))

        # Build context (simplified - no thread/invoice needed)
        context = {
            "ocr_text": ocr_text,
        }

        # Use prompt's get_messages() - handles rendering, validation, and parsing
        messages = assistant.prompt_id.get_messages(context)

        return messages, assistant

    @api.model
    def _call_llm_for_extraction(self, prepend_messages, assistant):
        """Call LLM directly without thread abstraction

        This method calls the LLM model directly for one-shot extraction
        without creating a thread. It uses non-streaming mode for simplicity.

        The provider returns a standardized response dict:
        {"content": "text response", "tool_calls": [...]}

        Args:
            prepend_messages (list): Rendered prompt messages
            assistant (llm.assistant): Assistant record for model/provider

        Returns:
            str: LLM response text

        Raises:
            UserError: If LLM call fails or returns invalid format
        """
        # Call model.chat() directly (no streaming needed for one-shot)
        # Returns standardized dict: {"content": "...", "tool_calls": [...]}
        response = assistant.model_id.chat(
            messages=[],  # No conversation history for one-shot
            tools=False,  # No tool calling needed
            stream=False,  # Non-streaming for simplicity
            prepend_messages=prepend_messages,
        )

        # Extract content from standardized response dict
        if isinstance(response, dict) and "content" in response:
            content = response.get("content", "")
            if content:
                return content

        # Fallback error if response format is unexpected
        raise UserError(_(
            "Invalid LLM Response Format\n\n"
            "The LLM returned an unexpected response format.\n\n"
            "Expected: dict with 'content' key\n"
            "Received: %s\n\n"
            "This could indicate:\n"
            "1. Model configuration issue\n"
            "2. Provider API changes\n"
            "3. Network/connection problem\n\n"
            "Please check logs for detailed error information"
        ) % type(response).__name__)

    @api.model
    def _parse_llm_response(self, llm_response_text):
        """Parse JSON from LLM response

        Extracts and parses JSON data from LLM response, handling both
        code-block wrapped JSON and raw JSON formats.

        Args:
            llm_response_text (str): Raw LLM response

        Returns:
            dict: Parsed invoice data, or None if parsing failed
        """
        # Extract JSON from code blocks or raw text
        json_match = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```", llm_response_text, re.DOTALL
        )
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON
            json_match = re.search(r"\{.*\}", llm_response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                _logger.error("No JSON found in LLM response")
                return None

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            _logger.error(f"Failed to parse JSON: {e}")
            return None
