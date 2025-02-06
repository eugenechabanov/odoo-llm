from typing import Any, List, Optional, Type, Dict
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

class MISStyleConfig(BaseModel):
    """Style configuration for MIS report elements"""
    name: str = Field(..., description="Name of the style")
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="""
        Style properties as key-value pairs. Supported properties:
        - font_weight: normal, bold
        - font_style: normal, italic
        - color: CSS color for text
        - background_color: CSS color for background
        - prefix: Value prefix (e.g., $, €)
        - suffix: Value suffix (e.g., %, USD)
        - indent_level: Integer for indentation
        - dp: Number of decimal places
        """
    )

class MISKPIConfig(BaseModel):
    """Configuration for a single KPI in MIS report template"""
    name: str = Field(
        ..., 
        description="Technical name of the KPI (must be a valid Python identifier)"
    )
    description: str = Field(
        ..., 
        description="Human-readable description of the KPI"
    )
    expression: str = Field(
        ...,
        description="""
        Accounting expression for KPI calculation. Examples:
        - Account balances: balp[account_code%] (e.g., balp[7%] for revenue accounts)
        - Arithmetic: +, -, *, / (e.g., revenue + expenses)
        - References: Other KPI names (e.g., gross_profit + operating_expenses)
        - Functions: sum(), avg() (e.g., sum(balp[60%,61%]))
        """
    )
    type: str = Field(
        default="num",
        description="""
        Type of KPI value:
        - num: Numeric value
        - pct: Percentage
        - str: String
        """
    )
    compare_method: str = Field(
        default="pct",
        description="""
        How to compare values between periods:
        - diff: Absolute difference
        - pct: Percentage difference
        - none: No comparison
        """
    )
    accumulation_method: str = Field(
        default="sum",
        description="""
        How to accumulate values over time:
        - sum: Add values
        - avg: Average values
        - none: No accumulation
        """
    )
    sequence: Optional[int] = Field(
        None,
        description="Display order (lower numbers first)"
    )
    style: Optional[MISStyleConfig] = Field(
        None,
        description="Style configuration for this KPI"
    )
    show_account_details: bool = Field(
        default=False,
        description="Whether to expand and show individual account details"
    )

class MISTemplateConfig(BaseModel):
    """Configuration for MIS report template"""
    name: str = Field(
        ...,
        description="Name of the template"
    )
    description: Optional[str] = Field(
        None,
        description="Detailed description of the template's purpose"
    )
    default_style: Optional[MISStyleConfig] = Field(
        None,
        description="Default style for all KPIs in the template"
    )
    kpis: List[MISKPIConfig] = Field(
        ...,
        description="List of KPIs to include in the template"
    )

class MISTemplateGenerator(BaseTool):
    """Tool for generating MIS report templates in Odoo"""
    
    name: str = "MIS Report Template Generator"
    description: str = """
    Creates Management Information System (MIS) report templates in Odoo.
    This tool creates only the template structure, not the actual report instances.
    
    Templates can be used to generate various financial reports such as:
    - Profit and Loss Statement
    - Balance Sheet
    - Cash Flow Statement
    - Sales Analysis
    - Expense Report
    - Custom Financial Reports
    
    The tool requires:
    1. Template information (name, description)
    2. List of KPIs with:
       - Technical name (valid Python identifier)
       - Description
       - Calculation expression
       - Display preferences
    3. Optional styling configuration
    
    Expression Examples:
    1. Account balances:
       - Revenue: -balp[7%]
       - Expenses: balp[6%]
    2. Calculations:
       - Gross Profit: revenue + cogs
       - Profit Margin: gross_profit / revenue * 100
    3. Complex formulas:
       - Operating Income: sum(balp[70%,71%,72%]) + other_income
    """
    
    args_schema: Type[BaseModel] = MISTemplateConfig
    env: Any = Field(description="Odoo environment")

    def __init__(self, env: Any, **kwargs: Any) -> None:
        """Initialize with Odoo environment"""
        super().__init__(env=env, **kwargs)
        self._report_model = env['mis.report']
        self._kpi_model = env['mis.report.kpi']
        self._expression_model = env['mis.report.kpi.expression']
        self._style_model = env['mis.report.style']

    def _create_style(self, config: MISStyleConfig) -> Any:
        """Create style record from configuration"""
        style_vals = {'name': config.name}
        
        for key, value in config.properties.items():
            if value is not None:
                style_vals[key] = value
                style_vals[f'{key}_inherit'] = False
                
        return self._style_model.create(style_vals)

    def _create_kpi(self, report_id: int, config: MISKPIConfig, default_style_id: Optional[int] = None) -> Any:
        """Create KPI record from configuration"""
        # Create KPI style if specified
        style_id = default_style_id
        if config.style:
            style = self._create_style(config.style)
            style_id = style.id

        # Create KPI
        kpi_vals = {
            'report_id': report_id,
            'name': config.name,
            'description': config.description,
            'type': config.type,
            'compare_method': config.compare_method,
            'accumulation_method': config.accumulation_method,
            'sequence': config.sequence or 10,
            'style_id': style_id,
            'auto_expand_accounts': config.show_account_details,
        }
        
        kpi = self._kpi_model.create(kpi_vals)

        # Create expression
        self._expression_model.create({
            'kpi_id': kpi.id,
            'name': config.expression
        })

        return kpi

    def _run(
        self,
        name: str,
        description: Optional[str] = None,
        default_style: Optional[MISStyleConfig] = None,
        kpis: List[MISKPIConfig] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Generate MIS report template in Odoo"""
        try:
            # Create default style if specified
            style_id = None
            if default_style:
                style = self._create_style(default_style)
                style_id = style.id

            # Create template
            template = self._report_model.create({
                'name': name,
                'description': description,
                'style_id': style_id,
            })

            # Create KPIs
            for kpi_config in kpis:
                self._create_kpi(template.id, kpi_config, style_id)

            return {
                'success': True,
                'message': f"Successfully created MIS report template '{name}'",
                'template_id': template.id
            }

        except Exception as e:
            return {
                'success': False,
                'message': f"Error creating template: {str(e)}",
                'error_details': {'exception': str(e)}
            }