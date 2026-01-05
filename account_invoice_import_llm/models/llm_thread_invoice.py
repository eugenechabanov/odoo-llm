import logging
from odoo import models

_logger = logging.getLogger(__name__)


class LLMThreadInvoice(models.Model):
    """Custom thread for invoice processing with dynamic OCR context"""

    _inherit = "llm.thread"

    def get_context(self, base_context=None):
        """Override to compute OCR text dynamically from invoice attachments

        This method supports two modes:
        1. Decoder mode: Attachment ID passed via context (before attachment is linked)
        2. Manual mode: Search for attachment on invoice (for manual trigger button)

        Returns:
            dict: Context with computed 'ocr_text' key for invoice threads
        """
        context = super().get_context(base_context)

        # Only for invoice threads
        if self.model == "account.move" and self.res_id:
            attachment = None

            # Priority 1: Check if attachment passed via context (decoder mode)
            attachment_id = self.env.context.get('llm_invoice_attachment_id')
            if attachment_id:
                attachment = self.env["ir.attachment"].browse(attachment_id)
                if not attachment.exists():
                    attachment = None

            # Priority 2: Search for attachment on invoice (manual mode, OCA wizard)
            if not attachment:
                invoice = self.env["account.move"].browse(self.res_id)
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
                # Compute OCR on-the-fly (raises exception if fails)
                ocr_text = self._compute_ocr_for_attachment(attachment)
                context["ocr_text"] = ocr_text

        return context

    def _compute_ocr_for_attachment(self, attachment):
        """Run Mistral OCR on attachment and return extracted text

        Args:
            attachment (ir.attachment): Invoice attachment to process

        Returns:
            str: Extracted text from OCR

        Raises:
            Exception: If OCR tool not found or OCR processing fails
        """
        # Get Mistral OCR tool (llm.tool with implementation llm_tool_ocr_mistral)
        ocr_tool = self.env["llm.tool"].search(
            [("implementation", "=", "llm_tool_ocr_mistral")], limit=1
        )
        if not ocr_tool:
            raise RuntimeError("Mistral OCR tool not found in system")

        # Call OCR via tool's public execute method
        results = ocr_tool.llm_tool_ocr_mistral_execute([attachment.id])

        if not results or len(results) == 0:
            raise RuntimeError(f"OCR returned no results for {attachment.name}")

        result = results[0]

        # Check for errors
        if result.get("error"):
            raise RuntimeError(
                f"OCR error for {attachment.name}: {result.get('error')}"
            )

        return result.get("extracted_text", "")
