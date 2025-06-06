from odoo import api, fields, models


class LLMThread(models.Model):
    _inherit = "llm.thread"

    locked = fields.Boolean(default=False)
    job_id = fields.Many2one("llm.job", string="Running Job")
    async_generation = fields.Boolean(string="Asynchronous Generation", default=False)

    # def generate(self, messages=None, system_prompt=None, **kwargs):
    #     """Generate content in the thread"""
    #     provider = self.provider_id
    #
    #     if provider.supports_async_generation() and self.async_generation:
    #         return provider.create_async_generation_job(
    #             messages, self, system_prompt=system_prompt, **kwargs
    #         )
    #     else:
    #         # Existing synchronous behavior
    #         content = provider.chat(messages, system_prompt=system_prompt, **kwargs)
    #         self.message_post(body=content)
    #         return content
