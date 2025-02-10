from typing import Any

from crewai.tools import BaseTool

from .mis_report_gen_tool import MISReportInstanceGenTool
from .mis_template_gen_tool import MISTemplateGenTool


class OdooMisToolSet:
    """Collection of MIS-related tools for Odoo"""

    def __init__(self, env: Any) -> None:
        """Initialize with Odoo environment

        Args:
            env: Odoo environment
        """
        self._env = env

    def get_tools(self) -> list[BaseTool]:
        """Get list of available MIS tools

        Returns:
            List[BaseTool]: List of MIS-related tools
        """
        return [
            MISTemplateGenTool(env=self._env),
            MISReportInstanceGenTool(env=self._env),
        ]
