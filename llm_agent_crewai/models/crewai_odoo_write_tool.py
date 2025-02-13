from odoo import api, models
from .odoo_tools.write_tool import OdooWriteTool


class LLMAgentTool(models.Model):
    """Extends the base tool model to support CrewAI write tool."""
    _inherit = 'llm.agent.tool'

    @api.model
    def _get_available_services(self):
        """Add CrewAI write tool service."""
        services = super()._get_available_services()
        services.append(('crewai_odoo_write_tool', 'CrewAI Odoo Write'))
        return services

    def crewai_odoo_write_tool_get_instance(self, **kwargs):
        """Get a CrewAI Tool instance for Odoo write operations."""
        self.ensure_one()
        return OdooWriteTool(env=self.env)
