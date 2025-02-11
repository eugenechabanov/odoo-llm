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
            records = self._env[model].search_read(
                domain=domain,
                fields=fields,
                limit=limit,
                offset=offset,
                order=order
            )
            return {
                'result': 'success',
                'records': records,
                'message': f'Found {len(records)} records in {model}'
            }
        except Exception as e:
            return {
                'result': 'error',
                'error': str(e),
                'message': f'Error searching records in {model}'
            }

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
                'result': 'success',
                'id': record.id,
                'message': f'Record created successfully in {model}'
            }
        except Exception as e:
            return {
                'result': 'error',
                'error': str(e),
                'message': f'Error creating record in {model}'
            }

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
                'result': 'success',
                'ids': ids,
                'message': f'Records updated successfully in {model}'
            }
        except Exception as e:
            return {
                'result': 'error',
                'error': str(e),
                'message': f'Error updating records in {model}'
            }

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
                'result': 'success',
                'ids': ids,
                'message': f'Records deleted successfully from {model}'
            }
        except Exception as e:
            return {
                'result': 'error',
                'error': str(e),
                'message': f'Error deleting records from {model}'
            }
