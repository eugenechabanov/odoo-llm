from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)
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
    kpis: List[MISKPIConfig] = Field(
        ...,
        description="List of KPIs to include in the template"
    )

class MISTemplateGenerator(BaseTool):
    """Generator for MIS report templates"""
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
       - Type (num, pct, str)
       - Optional comparison and accumulation methods
    
    1. Account balances:
       - Revenue: -balp[7%]
       - Expenses: balp[6%]
    2. Calculations:
       - Gross Profit: revenue + cogs
       - Profit Margin: gross_profit / revenue * 100
    3. Complex formulas:
       - Operating Income: sum(balp[70%,71%,72%]) + other_income

    The following special elements are recognized in the expressions to compute accounting data: {bal|crd|deb|pbal|nbal|fld}{pieu}(.fieldname)[account selector][journal items domain].

    bal, crd, deb, pbal, nbal, fld : balance, debit, credit, positive balance, negative balance, other numerical field.
    p, i, e : respectively variation over the period, initial balance, ending balance
    when fld is used : a field name specifier must be provided (e.g. fldp.quantity
    The account selector is a like expression on the account code (eg 70%, etc), or a domain over accounts (eg [('code', 'like', '60%')]).
    The journal items domain is an Odoo domain filter on journal items.
    balu[] : (u for unallocated) is a special expression that shows the unallocated profit/loss of previous fiscal years.
    Expressions can involve other KPI, sub KPI and query results by name (eg kpi1 + kpi2, kpi2.subkpi1, query1.field1).

    Additionally following variables are available in the evaluation context:

    sum, min, max, len, avg : behave as expected, very similar to the python builtins.
    datetime, datetime, dateutil : the python modules.
    date_from, date_to : beginning and end date of the period.
    AccountingNone : a null value that behaves as 0 in arithmetic operations.
    Expression Examples:
    bal[70] : variation of the balance of account 70 over the period (it is the same as balp[70].
    bali[70,60] : initial balance of accounts 70 and 60.
    bale[1%] : balance of accounts starting with 1 at end of period.
    crdp[40%] : sum of all credits on accounts starting with 40 during the period.
    debp[55%][('journal_id.code', '=', 'BNK1')] : sum of all debits on accounts 55 and journal BNK1 during the period.
    balp[('user_type_id', '=', ref('account. data_account_type_receivable').id)][] : variation of the balance of all receivable accounts over the period.
    balp[][('tax_line_id.tag_ids', '=', ref('l10n_be.tax_tag_56').id)] : balance of move lines related to tax grid 56.
    pbale[55%] : sum of all ending balances of accounts starting with 55 whose ending balance is positive.
    Example expressions:

    Example KPI:
    {
        "name": "gross_profit",
        "description": "Gross Profit",
        "expression": "revenue + cogs",
        "type": "num",
        "compare_method": "pct",
        "sequence": 30
    }
    """
    name: str = "MIS Template Generator for Odoo"
    args_schema: Type[BaseModel] = MISTemplateConfig

    def __init__(self, env: Any, **kwargs: Any) -> None:
        """Initialize with Odoo environment"""
        super().__init__(env=env, **kwargs)
        self._env = env
        self._report_model = env['mis.report']
        self._kpi_model = env['mis.report.kpi']
        self._expression_model = env['mis.report.kpi.expression']

    def _create_kpi(self, report_id: int, config: MISKPIConfig) -> Any:
        """Create a KPI record"""
        kpi_vals = {
            'report_id': report_id,
            'name': config.name,
            'description': config.description,
            'type': config.type,
            'compare_method': config.compare_method,
            'accumulation_method': config.accumulation_method,
            'sequence': config.sequence or 10,
            'auto_expand_accounts': config.show_account_details,
        }
        kpi = self._kpi_model.create(kpi_vals)
        self._expression_model.create({
            'kpi_id': kpi.id,
            'name': config.expression
        })
        return kpi

    def _run(
        self,
        name: str,
        description: Optional[str] = None,
        kpis: List[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Generate MIS report template in Odoo"""
        try:
            # Convert input to MISTemplateConfig
            template_config = MISTemplateConfig(
                name=name,
                description=description,
                kpis=[MISKPIConfig(**kpi) for kpi in (kpis or [])]
            )
            
            # Create template
            template = self._report_model.create({
                'name': template_config.name + datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
                'description': template_config.description,
                'style_id': 3  # Using hardcoded style ID
            })

            # Create KPIs
            for kpi_config in template_config.kpis:
                self._create_kpi(template.id, kpi_config)

            return {
                'success': True,
                'message': f"Successfully created MIS report template '{template_config.name}'",
                'template_id': template.id
            }

        except Exception as e:
            _logger.error(e)
            return {
                'success': False,
                'message': f"Error creating template: {str(e)}",
                'error_details': {'exception': str(e)}
            }
