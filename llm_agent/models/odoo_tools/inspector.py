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
    Analyzes Odoo modules to understand their structure, models, and relationships.
    Can inspect module manifests, model definitions, security rules, and views.
    """
    _module_cache: Dict[str, Dict[str, Any]]
    
    def __init__(self, env: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._env = env
        self._module_cache = {}
    
    class InspectSchema(BaseModel):
        module_name: str = Field(..., description="Name of the Odoo module to inspect")
        include_source: bool = Field(
            False, 
            description="Whether to include source code of models"
        )
        
    args_schema: Type[BaseModel] = InspectSchema
    
    def _find_module_path(self, module_name: str) -> Optional[str]:
        """Find the filesystem path for a given module"""
        module = self._env['ir.module.module'].search([('name', '=', module_name)], limit=1)
        if not module:
            return None
            
        # Check common module locations
        addons_paths = self._env['ir.module.module']._get_addons_path()
        for addons_path in addons_paths:
            module_path = os.path.join(addons_path, module_name)
            if os.path.isdir(module_path):
                return module_path
        return None
    
    def _parse_manifest(self, module_path: str) -> Dict:
        """Parse the module's manifest file"""
        manifest_path = os.path.join(module_path, '__manifest__.py')
        if not os.path.exists(manifest_path):
            manifest_path = os.path.join(module_path, '__openerp__.py')
            
        if not os.path.exists(manifest_path):
            return {}
            
        with open(manifest_path, 'r') as f:
            manifest_content = f.read()
            
        try:
            return ast.literal_eval(manifest_content)
        except:
            return {}
    
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
                            # Analyze fields and methods
                            fields = {}
                            methods = []
                            
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
                                                        'args': [ast.unparse(arg) for arg in child.value.args],
                                                        'kwargs': {
                                                            kw.arg: ast.unparse(kw.value) 
                                                            for kw in child.value.keywords
                                                        }
                                                    }
                                                    
                                elif isinstance(child, ast.FunctionDef):
                                    methods.append({
                                        'name': child.name,
                                        'args': [arg.arg for arg in child.args.args if arg.arg != 'self'],
                                        'decorators': [ast.unparse(d) for d in child.decorator_list]
                                    })
                                    
                            models_info[model_name] = {
                                'fields': fields,
                                'methods': methods
                            }
                            
        except Exception as e:
            print(f"Error parsing {file_path}: {str(e)}")
            
        return models_info
    
    def _analyze_security(self, module_path: str) -> Dict:
        """Analyze security files (ir.model.access.csv and record rules)"""
        security_info = {
            'access_rights': [],
            'record_rules': []
        }
        
        # Check ir.model.access.csv
        access_path = os.path.join(module_path, 'security/ir.model.access.csv')
        if os.path.exists(access_path):
            import csv
            with open(access_path, 'r') as f:
                reader = csv.DictReader(f)
                security_info['access_rights'] = list(reader)
                
        # Check security rules
        security_path = os.path.join(module_path, 'security')
        if os.path.exists(security_path):
            for file in os.listdir(security_path):
                if file.endswith('.xml'):
                    security_info['record_rules'].append(file)
                    
        return security_info
    
    def _analyze_views(self, module_path: str) -> List[Dict]:
        """Analyze view definitions"""
        views = []
        views_path = os.path.join(module_path, 'views')
        if os.path.exists(views_path):
            for file in os.listdir(views_path):
                if file.endswith('.xml'):
                    views.append(file)
        return views
    
    def _run(self, module_name: str, include_source: bool = False) -> Dict:
        """Execute module inspection"""
        try:
            # Check cache first
            if module_name in self._module_cache:
                return self._module_cache[module_name]
                
            module_path = self._find_module_path(module_name)
            if not module_path:
                return f"Module {module_name} not found"
                
            # Parse manifest
            manifest = self._parse_manifest(module_path)
            
            # Analyze models
            models_info = {}
            models_dir = os.path.join(module_path, 'models')
            if os.path.exists(models_dir):
                for file in os.listdir(models_dir):
                    if file.endswith('.py') and file != '__init__.py':
                        file_models = self._analyze_model_file(os.path.join(models_dir, file))
                        models_info.update(file_models)
            
            # Get security info
            security_info = self._analyze_security(module_path)
            
            # Get views
            views = self._analyze_views(module_path)
            
            # Compile module info
            module_info = ModuleInfo(
                name=module_name,
                version=manifest.get('version', ''),
                category=manifest.get('category', ''),
                depends=manifest.get('depends', []),
                description=manifest.get('description', ''),
                models=models_info,
                views=views,
                security=security_info
            )
            
            # Cache the results
            self._module_cache[module_name] = module_info.dict()
            
            return self._module_cache[module_name]
            
        except Exception as e:
            return f"Error inspecting module: {str(e)}"
