import logging
from odoo import models

_logger = logging.getLogger(__name__)


class LLMThreadInvoice(models.Model):
    """Custom thread for invoice processing with dynamic OCR context"""

    _inherit = "llm.thread"

    def get_context(self, base_context=None):
        """Override to compute OCR text dynamically from invoice attachments

        This method is called by get_prepend_messages() when building the prompt.
        It computes OCR text on-the-fly from the invoice's attachment, allowing
        dynamic context injection via {{ ocr_text }} in assistant's default_values.

        Returns:
            dict: Context with computed 'ocr_text' key for invoice threads
        """
        context = super().get_context(base_context)

        # Only for invoice threads
        if self.model == "account.move" and self.res_id:
            invoice = self.env["account.move"].browse(self.res_id)

            # Get first PDF/image attachment
            attachment = self.env["ir.attachment"].search(
                [
                    ("res_model", "=", "account.move"),
                    ("res_id", "=", invoice.id),
                    (
                        "mimetype",
                        "in",
                        ["application/pdf", "image/png", "image/jpeg", "image/jpg"],
                    ),
                ],
                limit=1,
            )

            if attachment:
                # Compute OCR on-the-fly
                ocr_text = self._compute_ocr_for_attachment(attachment)
                if ocr_text:
                    # Add to context for dynamic defaults evaluation
                    context["ocr_text"] = ocr_text
                    _logger.info(
                        f"Computed OCR text for invoice {invoice.name or 'Draft'} "
                        f"from attachment {attachment.name} ({len(ocr_text)} chars)"
                    )

        return context

    def _compute_ocr_for_attachment(self, attachment):
        """Run Mistral OCR on attachment and return extracted text

        Args:
            attachment (ir.attachment): Invoice attachment to process

        Returns:
            str: Extracted text from OCR, or None if failed
        """
        try:
            # Get Mistral OCR tool (llm.tool with implementation llm_tool_ocr_mistral)
            ocr_tool = self.env["llm.tool"].search(
                [("implementation", "=", "llm_tool_ocr_mistral")], limit=1
            )
            if not ocr_tool:
                _logger.warning("Mistral OCR tool not found in system")
                return None

            # Call OCR via tool's public execute method
            results = ocr_tool.llm_tool_ocr_mistral_execute([attachment.id])

            if not results or len(results) == 0:
                _logger.warning(f"OCR returned no results for {attachment.name}")
                return None

            result = results[0]

            # Check for errors
            if result.get("error"):
                _logger.error(
                    f"OCR error for {attachment.name}: {result.get('error')}"
                )
                return None

            extracted_text = result.get("extracted_text", "")
            if extracted_text:
                _logger.info(
                    f"OCR extracted {len(extracted_text)} chars from {attachment.name}"
                )
            else:
                _logger.warning(f"OCR returned empty text for {attachment.name}")

            return extracted_text

        except Exception as e:
            _logger.error(
                f"OCR failed for attachment {attachment.id}: {e}", exc_info=True
            )
            return None
