import os
import ast
from typing import Dict, List, Optional, Any, Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from .schemas import ModuleInfo

class OdooModuleInspectorTool(BaseTool):
    """Tool for inspecting Odoo modules and their components"""
    
    name: str = "Odoo Module Inspector"
    description: str = """
    Analyzes Odoo modules to understand their models and fields.
    Provides information about model structure and field definitions.
    """
    
    def __init__(self, env: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._env = env
        self._module_cache = {}
    
    class InspectSchema(BaseModel):
        module_name: str = Field(..., description="Name of the Odoo module to inspect")
        
    args_schema: Type[BaseModel] = InspectSchema
    
    def _find_module_path(self, module_name: str) -> Optional[str]:
        """Find the filesystem path for a given module"""
        module = self._env['ir.module.module'].search([('name', '=', module_name)], limit=1)
        if not module:
            return None
            
        addons_paths = self._env['ir.module.module']._get_addons_path()
        for addons_path in addons_paths:
            module_path = os.path.join(addons_path, module_name)
            if os.path.isdir(module_path):
                return module_path
        return None
    
    def _analyze_model_file(self, file_path: str) -> Dict:
        """Analyze a Python file containing model definitions"""
        models_info = {}
        
        with open(file_path, 'r') as f:
            content = f.read()
            
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Check if class inherits from Model
                    is_model = False
                    model_name = None
                    
                    for base in node.bases:
                        if isinstance(base, ast.Name) and base.id in ['Model', 'TransientModel']:
                            is_model = True
                            break
                            
                    if is_model:
                        # Try to find _name attribute
                        for child in node.body:
                            if isinstance(child, ast.Assign):
                                for target in child.targets:
                                    if isinstance(target, ast.Name) and target.id == '_name':
                                        if isinstance(child.value, ast.Constant):
                                            model_name = child.value.value
                                            
                        if model_name:
                            # Analyze fields
                            fields = {}
                            
                            for child in node.body:
                                if isinstance(child, ast.Assign):
                                    # Field definitions
                                    for target in child.targets:
                                        if isinstance(target, ast.Name):
                                            field_name = target.id
                                            if isinstance(child.value, ast.Call):
                                                field_type = None
                                                if isinstance(child.value.func, ast.Name):
                                                    field_type = child.value.func.id
                                                elif isinstance(child.value.func, ast.Attribute):
                                                    field_type = child.value.func.attr
                                                    
                                                if field_type:
                                                    fields[field_name] = {
                                                        'type': field_type,
                                                        'kwargs': {
                                                            kw.arg: ast.unparse(kw.value) 
                                                            for kw in child.value.keywords
                                                        }
                                                    }
                                                    
                            models_info[model_name] = {
                                'fields': fields
                            }
                            
        except Exception as e:
            print(f"Error parsing {file_path}: {str(e)}")
            
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
                
            # Analyze models
            models_info = {}
            models_dir = os.path.join(module_path, 'models')
            if os.path.exists(models_dir):
                for file in os.listdir(models_dir):
                    if file.endswith('.py') and file != '__init__.py':
                        file_models = self._analyze_model_file(os.path.join(models_dir, file))
                        models_info.update(file_models)
            
            # Compile module info
            module_info = ModuleInfo(
                name=module_name,
                models=models_info
            )
            
            # Cache the results
            self._module_cache[module_name] = module_info.dict()
            
            return self._module_cache[module_name]
            
        except Exception as e:
            return f"Error inspecting module: {str(e)}"
