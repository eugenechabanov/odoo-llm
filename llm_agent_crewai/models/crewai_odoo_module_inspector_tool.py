from odoo import api, models
from .odoo_tools.module_inspector_tool import OdooModuleInspectorTool


class LLMAgentTool(models.Model):
    """Extends the base tool model to support CrewAI module inspector tool."""
    _inherit = 'llm.agent.tool'

    @api.model
    def _get_available_services(self):
        """Add CrewAI module inspector tool service."""
        services = super()._get_available_services()
        services.append(('crewai_odoo_module_inspector_tool', 'CrewAI Odoo Module Inspector'))
        return services

    def crewai_odoo_module_inspector_tool_get_instance(self, **kwargs):
        """Get a CrewAI Tool instance for Odoo module inspection."""
        self.ensure_one()
        return OdooModuleInspectorTool(env=self.env)
