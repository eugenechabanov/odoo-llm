from odoo import api, models
from .odoo_tools.search_tool import OdooSearchTool


class LLMAgentTool(models.Model):
    """Extends the base tool model to support CrewAI search tool."""
    _inherit = 'llm.agent.tool'

    @api.model
    def _get_available_services(self):
        """Add CrewAI search tool service."""
        services = super()._get_available_services()
        services.append(('crewai_odoo_search_tool', 'CrewAI Odoo Search'))
        return services

    def crewai_odoo_search_tool_get_instance(self, **kwargs):
        """Get a CrewAI Tool instance for Odoo search operations."""
        self.ensure_one()
        return OdooSearchTool(env=self.env)
