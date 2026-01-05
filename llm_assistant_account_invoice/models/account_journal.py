import logging
from odoo import models

_logger = logging.getLogger(__name__)


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def _create_document_from_attachment(self, attachment_ids=None):
        """Override to add detailed logging for decoder chain execution"""
        _logger.info(
            f"\n{'='*80}\n"
            f"📄 JOURNAL._create_document_from_attachment() CALLED\n"
            f"{'='*80}\n"
            f"Journal: {self.name}\n"
            f"Attachment IDs: {attachment_ids}\n"
            f"{'='*80}"
        )

        attachments = self.env['ir.attachment'].browse(attachment_ids)
        for attachment in attachments:
            _logger.info(
                f"🔍 Processing attachment: {attachment.name}\n"
                f"   - ID: {attachment.id}\n"
                f"   - Mimetype: {attachment.mimetype}\n"
                f"   - Res Model: {attachment.res_model}\n"
                f"   - Res ID: {attachment.res_id}\n"
            )

        # Call parent (which will trigger decoder chain)
        _logger.info("⚙️  Calling parent _create_document_from_attachment...")
        result = super()._create_document_from_attachment(attachment_ids)

        _logger.info(
            f"✅ _create_document_from_attachment COMPLETED\n"
            f"   - Created invoices: {result.ids if result else 'None'}\n"
            f"   - Count: {len(result) if result else 0}"
        )

        return result
