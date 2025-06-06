from odoo import api, fields, models

class LLMGenerateJob(models.Model):
    _name = "llm.generate.job"
    _description = "LLM Generation Job"
    _inherit = ["llm.job.mixin"]

    model_id = fields.Many2one("llm.model", string="Model")
    messages = fields.Text(string="Input Messages")
    prompt = fields.Text(string="System Prompt")

    def process_result(self, result):
        """Process the result and update the thread"""
        if self.thread_id and result:
            self.thread_id.message_post(body=result)
            self.thread_id.write({'locked': False, 'job_id': False})
        return True
