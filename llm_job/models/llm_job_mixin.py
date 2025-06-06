from odoo import api, fields, models
import logging
_logger = logging.getLogger(__name__)
class LLMJobMixin(models.AbstractModel):
    _name = "llm.job.mixin"
    _description = "Base Job for LLM"
    _inherit = ["mail.thread"]

    name = fields.Char(required=True)
    provider_id = fields.Many2one("llm.provider", required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('queued', 'Queued'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled')
    ], default='draft', tracking=True)

    external_job_id = fields.Char(string="External Job ID")
    thread_id = fields.Many2one("llm.thread", string="Thread")

    start_time = fields.Datetime(string="Start Time")
    end_time = fields.Datetime(string="End Time")

    result = fields.Text(string="Result")
    error_message = fields.Text(string="Error Message")

    def check_status(self):
        """Check job status with the provider"""
        return self.provider_id._dispatch("check_job_status", self.external_job_id, record=self)


    @api.model
    def check_pending_jobs(self):
        """Method to check the status of all pending jobs"""
        pending_jobs = self.search([
            ('state', 'in', ['draft', 'queued', 'running'])
        ])
        for job in pending_jobs:
            if job.external_job_id:
                try:
                    job.check_status()
                except Exception as e:
                    _logger.error(f"Error trying to check status for job {job.id}: {e}")

        return True



