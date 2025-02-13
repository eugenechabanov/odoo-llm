from odoo import api, models
from .odoo_tools.create_tool import OdooCreateTool


class LLMAgentTool(models.Model):
    """Extends the base tool model to support CrewAI create tool."""
    _inherit = 'llm.agent.tool'
    # https://docs.crewai.com/concepts/tools#structured-tools
    # TODO: Check structured tool later
    @api.model
    def _get_available_services(self):
        """Add CrewAI create tool service."""
        services = super()._get_available_services()
        services.append(('crewai_odoo_create_tool', 'CrewAI Odoo Create'))
        return services

    def crewai_odoo_create_tool_get_instance(self, **kwargs):
        """Get a CrewAI Tool instance for Odoo create operations."""
        self.ensure_one()
        return OdooCreateTool(env=self.env)
