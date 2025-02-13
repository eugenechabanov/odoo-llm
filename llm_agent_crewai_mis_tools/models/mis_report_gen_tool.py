from odoo import api, models
from .tools.mis_report_gen import MISReportInstanceGenTool


class LLMAgentTool(models.Model):
    """Extends the base tool model to support CrewAI MIS report generator tool."""
    _inherit = 'llm.agent.tool'

    @api.model
    def _get_available_services(self):
        """Add CrewAI MIS report generator tool service."""
        services = super()._get_available_services()
        services.append(('crewai_mis_report_gen_tool', 'CrewAI MIS Report Generator'))
        return services

    def crewai_mis_report_gen_tool_get_instance(self, **kwargs):
        """Get a CrewAI Tool instance for MIS report generation."""
        self.ensure_one()
        return MISReportInstanceGenTool(env=self.env)
