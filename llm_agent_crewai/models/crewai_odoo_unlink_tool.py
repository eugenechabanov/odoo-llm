from odoo import api, models
from .odoo_tools.unlink_tool import OdooUnlinkTool


class LLMAgentTool(models.Model):
    """Extends the base tool model to support CrewAI unlink tool."""
    _inherit = 'llm.agent.tool'

    @api.model
    def _get_available_services(self):
        """Add CrewAI unlink tool service."""
        services = super()._get_available_services()
        services.append(('crewai_odoo_unlink_tool', 'CrewAI Odoo Unlink'))
        return services

    def crewai_odoo_unlink_tool_get_instance(self, **kwargs):
        """Get a CrewAI Tool instance for Odoo unlink operations."""
        self.ensure_one()
        return OdooUnlinkTool(env=self.env)
