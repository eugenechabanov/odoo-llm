from typing import List, Dict, Optional, Any, Type
from crewai.tools import BaseTool
from pydantic import BaseModel
from .schemas import (
    OdooSearchSchema,
    OdooCreateSchema,
    OdooWriteSchema,
    OdooUnlinkSchema
)

class OdooSearchTool(BaseTool):
    """Tool for searching records"""
    name: str = "Odoo Search"
    description: str = "Search for records in any Odoo model"
    args_schema: Type[BaseModel] = OdooSearchSchema

    def __init__(self, env: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._env = env

    def _run(
        self, 
        model: str,
        domain: List[tuple],
        fields: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        try:
            return self._env[model].search_read(
                domain=domain,
                fields=fields,
                limit=limit,
                offset=offset,
                order=order
            )
        except Exception as e:
            return f"Error searching records: {str(e)}"

class OdooCreateTool(BaseTool):
    """Tool for creating records"""
    name: str = "Odoo Create"
    description: str = "Create new records in any Odoo model"
    args_schema: Type[BaseModel] = OdooCreateSchema

    def __init__(self, env: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._env = env

    def _run(self, model: str, values: Dict[str, Any]) -> Dict[str, Any]:
        try:
            record = self._env[model].create(values)
            return {
                'id': record.id,
                'result': 'success',
                'message': f'Record created successfully in {model}'
            }
        except Exception as e:
            return f"Error creating record: {str(e)}"

class OdooWriteTool(BaseTool):
    """Tool for updating records"""
    name: str = "Odoo Write"
    description: str = "Update existing records in any Odoo model"
    args_schema: Type[BaseModel] = OdooWriteSchema

    def __init__(self, env: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._env = env

    def _run(self, model: str, ids: List[int], values: Dict[str, Any]) -> Dict[str, Any]:
        try:
            records = self._env[model].browse(ids)
            records.write(values)
            return {
                'ids': ids,
                'result': 'success',
                'message': f'Records updated successfully in {model}'
            }
        except Exception as e:
            return f"Error updating records: {str(e)}"

class OdooUnlinkTool(BaseTool):
    """Tool for deleting records"""
    name: str = "Odoo Unlink"
    description: str = "Delete records from any Odoo model"
    args_schema: Type[BaseModel] = OdooUnlinkSchema

    def __init__(self, env: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._env = env

    def _run(self, model: str, ids: List[int]) -> Dict[str, Any]:
        try:
            records = self._env[model].browse(ids)
            records.unlink()
            return {
                'ids': ids,
                'result': 'success',
                'message': f'Records deleted successfully from {model}'
            }
        except Exception as e:
            return f"Error deleting records: {str(e)}"
