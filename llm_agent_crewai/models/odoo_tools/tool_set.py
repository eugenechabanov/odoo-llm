from typing import List, Any
from crewai.tools import BaseTool
from .inspector import OdooModuleInspectorTool
from .crud import (
    OdooSearchTool,
    OdooCreateTool,
    OdooWriteTool,
    OdooUnlinkTool
)

class OdooToolSet:
    """Collection of Odoo tools for module inspection and CRUD operations"""

    def __init__(self, env: Any) -> None:
        self.env = env

    def get_tools(self) -> List[BaseTool]:
        """Returns a list of all available Odoo tools"""
        return [
            OdooModuleInspectorTool(self.env),
            OdooSearchTool(self.env),
            OdooCreateTool(self.env),
            OdooWriteTool(self.env),
            OdooUnlinkTool(self.env)
        ]
