from odoo import api, models


class LLMAgentToolProvider(models.Model):
    """Extends the base tool provider model to support CrewAI tools."""
    _inherit = 'llm.agent.tool.provider'

    @api.model
    def _get_available_services(self):
        """Add CrewAI service to available services."""
        services = super()._get_available_services()
        services.append(('crewai', 'CrewAI'))
        return services

    def crewai_get_instance(self, **kwargs):
        """Get a CrewAI tool provider instance.
        
        This method follows the service dispatch pattern from llm.service.mixin.
        The method name is prefixed with 'crewai_' to match the service code.
        """
        self.ensure_one()
        # For CrewAI, we don't need a special provider instance
        # The tools themselves will handle the CrewAI integration
        return self
