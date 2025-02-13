from odoo import api, models
from .tools.mis_template_gen import MISTemplateGenTool


class LLMAgentTool(models.Model):
    """Extends the base tool model to support CrewAI MIS template generator tool."""
    _inherit = 'llm.agent.tool'

    @api.model
    def _get_available_services(self):
        """Add CrewAI MIS template generator tool service."""
        services = super()._get_available_services()
        services.append(('crewai_mis_template_gen_tool', 'CrewAI MIS Template Generator'))
        return services

    def crewai_mis_template_gen_tool_get_instance(self, **kwargs):
        """Get a CrewAI Tool instance for MIS template generation."""
        self.ensure_one()
        return MISTemplateGenTool(env=self.env)
