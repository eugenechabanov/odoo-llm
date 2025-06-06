from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class LLMProvider(models.Model):
    _inherit = "llm.provider"

    # Add to the existing LLMProvider class
    def supports_async_generation(self):
        """Check if the provider supports asynchronous generation"""
        return self._dispatch("supports_async_generation", default=False)

    def create_async_generation_job(self, messages, thread, model=None, system_prompt=None, **kwargs):
        """Create asynchronous generation job"""
        if not self.supports_async_generation():
            raise UserError(_("This provider does not support asynchronous generation jobs"))

        if not model:
            model = self.get_model(model=model, model_use="chat")

        # Create job record
        job = self.env["llm.generate.job"].create({
            'name': f"Generation for {thread.name}",
            'provider_id': self.id,
            'thread_id': thread.id,
            'model_id': model.id if model else False,
            'messages': str(messages),
            'prompt': system_prompt,
        })

        # Queue the job with the provider
        external_job_id = self._dispatch(
            "queue_generation_job",
            messages,
            model=model,
            system_prompt=system_prompt,
            **kwargs
        )
        job.write({'external_job_id': external_job_id,'state': 'queued', 'start_time': fields.Datetime.now()})
        # Lock thread and post notification
        thread.write({'locked': True, 'job_id': job.id})
        thread.message_post(body=_("Generation job queued. Awaiting completion."))

        return job
