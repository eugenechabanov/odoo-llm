import os
from typing import Dict, Optional, Any, Type, ClassVar
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from odoo.modules import get_module_path, get_manifest
from .schemas import ModuleInfo

class OdooModuleInspectorTool(BaseTool):
    """Tool for inspecting Odoo modules and their components"""
    
    name: str = "Odoo Module Inspector"
    description: str = """
    Analyzes Odoo modules to understand their models and fields.
    Provides information about module manifest, model structure and field definitions.
    """
    
    # Maximum length for text fields to avoid token overflow
    MAX_TEXT_LENGTH: ClassVar[int] = 100
    
    def __init__(self, env: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._env = env
        self._module_cache = {}
    
    class InspectSchema(BaseModel):
        module_name: str = Field(..., description="Name of the Odoo module to inspect")
        
    args_schema: Type[BaseModel] = InspectSchema
    
    def _truncate_text(self, text: str, max_length: int = None) -> str:
        """Truncate text if it exceeds max_length and add indicator"""
        if not text:
            return ""
        max_length = max_length or self.MAX_TEXT_LENGTH
        if len(text) <= max_length:
            return text
        return text[:max_length] + "... (truncated)"
    
    def _find_module_path(self, module_name: str) -> Optional[str]:
        """Find the filesystem path for a given module"""
        module = self._env['ir.module.module'].search([('name', '=', module_name)], limit=1)
        if not module:
            return None
            
        module_path = get_module_path(module_name)
        if module_path and os.path.isdir(module_path):
            return module_path
            
        return None

    def _get_module_manifest(self, module_name: str) -> Dict:
        """Get the module's manifest information"""
        try:
            manifest = get_manifest(module_name) or {}
            # Truncate long text fields
            if 'description' in manifest:
                manifest['description'] = self._truncate_text(manifest['description'], max_length=500)
            if 'summary' in manifest:
                manifest['summary'] = self._truncate_text(manifest['summary'])
            return manifest
        except Exception as e:
            return {'error': str(e)}
    
    def _get_module_models(self, module_name: str) -> Dict:
        """Get all models and their fields for a given module"""
        models_info = {}
        
        # Find all models from this module's python files
        ir_model_data = self._env['ir.model.data'].search([
            ('module', '=', module_name),
            ('model', '=', 'ir.model')
        ])
        model_ids = ir_model_data.mapped('res_id')
        
        # Get the models
        models = self._env['ir.model'].browse(model_ids)
        
        for model in models:
            fields = {}
            for field in model.field_id:
                fields[field.name] = {
                    'type': field.ttype,
                    'kwargs': {
                        'string': self._truncate_text(field.field_description),
                        'required': field.required,
                        'readonly': field.readonly,
                        'store': field.store,
                        'help': self._truncate_text(field.help, max_length=200),  # Allow longer help text
                        'index': field.index,
                    }
                }
                # Add relation info if it's a relational field
                if field.ttype in ('many2one', 'one2many', 'many2many'):
                    fields[field.name]['kwargs']['relation'] = field.relation
                    if field.ttype in ('one2many', 'many2many'):
                        fields[field.name]['kwargs']['relation_field'] = field.relation_field
                
                # Remove empty or None values to reduce response size
                fields[field.name]['kwargs'] = {
                    k: v for k, v in fields[field.name]['kwargs'].items()
                    if v not in (False, None, "", [])
                }
                
            models_info[model.model] = {
                'fields': fields
            }
            
        return models_info
    
    def _run(self, module_name: str) -> Dict:
        """Execute module inspection"""
        try:
            # Check cache first
            if module_name in self._module_cache:
                return self._module_cache[module_name]
                
            module_path = self._find_module_path(module_name)
            if not module_path:
                return f"Module {module_name} not found"
                
            # Get models info directly from ir.model
            models_info = self._get_module_models(module_name)
            
            # Get manifest info
            manifest_info = self._get_module_manifest(module_name)
            
            # Compile module info
            module_info = ModuleInfo(
                name=module_name,
                models=models_info,
                manifest=manifest_info
            )
            
            # Cache the results
            self._module_cache[module_name] = module_info.dict()
            
            return self._module_cache[module_name]
            
        except Exception as e:
            return f"Error inspecting module: {str(e)}"
