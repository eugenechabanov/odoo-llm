from odoo import api, models
from .odoo_tools.orm import OdooORMTool


class LLMAgentTool(models.Model):
    """Extends the base tool model to support CrewAI ORM tool."""
    _inherit = 'llm.agent.tool'

    @api.model
    def _get_available_services(self):
        """Add CrewAI ORM tool service."""
        services = super()._get_available_services()
        services.append(('crewai_odoo_orm_tool', 'CrewAI Odoo ORM'))
        return services

    def crewai_odoo_orm_tool_get_instance(self, **kwargs):
        """Get a CrewAI Tool instance for Odoo ORM operations.
        
        This tool provides a unified interface for all common Odoo ORM operations:
        - search/search_read/search_count
        - create (single/batch)
        - write/unlink
        - copy/name_search
        - read_group with aggregations
        """
        self.ensure_one()
        return OdooORMTool(
            env=self.env,
            name=self.name,
            description=self.description
        )
