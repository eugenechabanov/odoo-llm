import logging
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from crewai.tools import BaseTool
import random
_logger = logging.getLogger(__name__)


class MISStyleConfig(BaseModel):
    """Configuration for MIS report style"""

    name: str | None = Field(
        None, description="Style name (if not provided, will use existing style)"
    )
    style_id: int | None = Field(None, description="ID of existing style to use")
    # color
    color: str = Field(
        default="#000000",
        description="Text color in valid RGB code (from #000000 to #FFFFFF)",
    )
    background_color: str = Field(
        default="#FFFFFF",
        description="Background color in valid RGB code (from #000000 to #FFFFFF)",
    )
    # font
    font_style: str = Field(
        default="normal",
        description="""
        Font style:
        - normal: Normal text
        - italic: Italic text
        """,
    )
    font_weight: str = Field(
        # type in the module, but we have to respect
        default="nornal",
        description="""
        Font weight:
        - nornal: Normal weight
        - bold: Bold text
        """,
    )
    font_size: str = Field(
        default="medium",
        description="""
        Font size:
        - medium: Default size
        - xx-small: Extra extra small
        - x-small: Extra small
        - small: Small
        - large: Large
        - x-large: Extra large
        - xx-large: Extra extra large
        """,
    )
    # indent
    indent_level: int = Field(default=0, description="Indentation level (must be >= 0)")
    # number format
    prefix: str | None = Field(None, description="Prefix to add before numbers")
    suffix: str | None = Field(None, description="Suffix to add after numbers")
    dp: int = Field(default=0, description="Number of decimal places for rounding")
    divider: str = Field(
        default="1",
        description="""
        Number scaling factor:
        - 1e-6: µ (micro)
        - 1e-3: m (milli)
        - 1: No scaling
        - 1e3: k (kilo)
        - 1e6: M (mega)
        """,
    )
    hide_empty: bool = Field(default=False, description="Hide when value is empty/zero")
    hide_always: bool = Field(default=False, description="Always hide this element")


class MISKPIConfig(BaseModel):
    """Configuration for a single KPI in MIS report template"""

    name: str = Field(
        ..., description="Technical name of the KPI (must be a valid Python identifier)"
    )
    description: str = Field(..., description="Human-readable description of the KPI")
    expression: str = Field(
        ...,
        description="""
        Accounting expression for KPI calculation. Examples:
        - Account balances: balp[account_code%] (e.g., balp[7%] for revenue accounts)
        - Arithmetic: +, -, *, / (e.g., revenue + expenses)
        - References: Other KPI names (e.g., gross_profit + operating_expenses)
        - Functions: sum(), avg() (e.g., sum(balp[60%,61%]))
        """,
    )
    type: str = Field(
        default="num",
        description="""
        Type of KPI value:
        - num: Numeric value
        - pct: Percentage
        - str: String
        """,
    )
    compare_method: str = Field(
        default="pct",
        description="""
        How to compare values between periods:
        - diff: Absolute difference
        - pct: Percentage difference
        - none: No comparison
        """,
    )
    accumulation_method: str = Field(
        default="sum",
        description="""
        How to accumulate values over time:
        - sum: Add values
        - avg: Average values
        - none: No accumulation
        """,
    )
    sequence: int | None = Field(
        None, description="Display order (lower numbers first)"
    )
    show_account_details: bool = Field(
        default=False,
        description="Whether to expand and show individual account details",
    )
    style: MISStyleConfig | None = Field(
        None, description="Style configuration for this KPI"
    )


class MISTemplateConfig(BaseModel):
    """Configuration for MIS report template"""

    name: str = Field(..., description="Name of the template")
    description: str | None = Field(
        None, description="Detailed description of the template's purpose"
    )
    kpis: list[MISKPIConfig] = Field(
        ..., description="List of KPIs to include in the template"
    )
    default_style: MISStyleConfig | None = Field(
        None, description="Default style for all KPIs in this template"
    )


class MISTemplateGenTool(BaseTool):
    """Generator for MIS report templates"""

    name: str = "MIS Template Generator for Odoo"
    description: str = """
    This tool generates MIS report templates with KPIs and styles. 
    Below we have some examples and documentation on how to use it.
    
    Standard KPIS for Balance Sheet Example:
    kpis: [
        {
          "name": "liabilities_equity",
          "description": "LIABILITIES + EQUITY",
          "expression": "liability_header+equity",
          "type": "num",
          "compare_method": "diff",
          "accumulation_method": "sum",
          "sequence": 20,
          "style": {"color": "#000000", "font_weight": "bold"}
        },
        {
          "name": "os",
          "description": "OFF BALANCE SHEET ACCOUNTS",
          "expression": "abs(bale[('account_type', '=', 'off_balance')])",
          "type": "num",
          "compare_method": "diff",
          "accumulation_method": "sum",
          "sequence": 21,
          "style": {"color": "#000000", "font_style": "italic"},
          "show_account_details": true
        },
        {
          "name": "assets",
          "description": "Assets",
          "expression": "current_assets + fixed_assets + non_current_assets",
          "type": "num",
          "compare_method": "diff",
          "accumulation_method": "sum",
          "sequence": 0,
          "style": {"color": "#000000", "font_weight": "bold"}
        },
        {
          "name": "current_assets",
          "description": "Current Assets",
          "expression": "bank_and_cash_accounts + receivables + current_assets_ca + prepayments",
          "type": "num",
          "compare_method": "diff",
          "accumulation_method": "sum",
          "sequence": 1,
          "style": {"color": "#000000", "font_style": "italic"}
        },
        {
          "name": "bank_and_cash_accounts",
          "description": "Bank and Cash Accounts",
          "expression": "bale[('account_type', '=', 'asset_cash')]",
          "type": "num",
          "compare_method": "diff",
          "accumulation_method": "sum",
          "sequence": 2,
          "style": {"color": "#000000", "font_style": "italic"},
          "show_account_details": true
        },
        {
          "name": "receivables",
          "description": "Receivables",
          "expression": "bale[('account_type', '=', 'asset_receivable'), ('non_trade', '=', False)]",
          "type": "num",
          "compare_method": "diff",
          "accumulation_method": "sum",
          "sequence": 3,
          "style": {"color": "#000000", "font_style": "italic"},
          "show_account_details": true
        },
    ]
     Standard KPIS for Profit And Loss statement Example:
     "kpis": [
        {
          "name": "net_profit",
          "description": "Net Profit",
          "expression": "op_inc + other_inc - cost_of_reven - expenses - depreciation",
          "type": "num",
          "compare_method": "diff",
          "accumulation_method": "sum",
          "sequence": 0,
          "style": {"color": "#000000", "font_weight": "bold"}
        },
        {
          "name": "income",
          "description": "Income",
          "expression": "op_inc + other_inc",
          "type": "num",
          "compare_method": "diff",
          "accumulation_method": "sum",
          "sequence": 1,
          "style": {"color": "#000000", "font_weight": "bold"}
        },
        {
          "name": "gross_profit",
          "description": "Gross Profit",
          "expression": "op_inc - cost_of_reven",
          "type": "num",
          "compare_method": "diff",
          "accumulation_method": "sum",
          "sequence": 2,
          "style": {"color": "#000000", "font_style": "italic"}
        },
        {
          "name": "op_inc",
          "description": "Operating Income",
          "expression": "-balp[('account_type', '=', 'income')][]",
          "type": "num",
          "compare_method": "diff",
          "accumulation_method": "sum",
          "sequence": 3,
          "style": {"color": "#000000", "font_style": "italic"},
          "show_account_details": true
        },
        {
          "name": "cost_of_reven",
          "description": "Cost of Revenue",
          "expression": "balp[('account_type', '=', 'expense_direct_cost')][]",
          "type": "num",
          "compare_method": "diff",
          "accumulation_method": "sum",
          "sequence": 4,
          "style": {"color": "#000000", "font_style": "italic"},
          "show_account_details": true
        }
    ]

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

    TIP: Use a negative sign (-balp[...]) for liabilities, revenues, and contra accounts to correctly subtract them in financial calculations. Do not use a negative sign for assets, expenses, and subtotals, as they naturally carry the correct balance for addition.
    And when computing another kpi using different KPIs, we can keep usual formulas for example: gross_profit = revenue - expenses.
    """
    args_schema: type[BaseModel] = MISTemplateConfig

    def __init__(self, env: Any, **kwargs: Any) -> None:
        """Initialize with Odoo environment"""
        super().__init__(env=env, **kwargs)
        self._env = env
        self._report_model = env["mis.report"]
        self._kpi_model = env["mis.report.kpi"]
        self._expression_model = env["mis.report.kpi.expression"]
        self._style_model = env["mis.report.style"]

    def _create_style(self, config: MISStyleConfig) -> int:
        """Create a style record"""
        if config.style_id:
            return config.style_id

        style_vals = {
            "name": config.name or f"Style_{random.randint(1, 100000)}",
            "color": config.color,
            "color_inherit": False if config.color else True,
            "background_color": config.background_color,
            "background_color_inherit": False if config.background_color else True,
            "font_style": config.font_style,
            "font_style_inherit": False if config.font_style else True,
            "font_weight": config.font_weight,
            "font_weight_inherit": False if config.font_weight else True,
            "font_size": config.font_size,
            "font_size_inherit": False if config.font_size else True,
            "indent_level": config.indent_level,
            "indent_level_inherit": False if config.indent_level else True,
            "prefix": config.prefix,
            "prefix_inherit": False if config.prefix else True,
            "suffix": config.suffix,
            "suffix_inherit": False if config.suffix else True,
            "dp": config.dp,
            "dp_inherit": False if config.dp else True,
            "divider": config.divider,
            "divider_inherit": False if config.divider else True,
            "hide_empty": config.hide_empty,
            "hide_always": config.hide_always,
        }

        style = self._style_model.create(style_vals)
        return style.id

    def _create_kpi(
        self, report_id: int, config: MISKPIConfig
    ) -> Any:
        """Create a KPI record"""
        style_id = None
        if config.style:
            style_id = self._create_style(config.style)

        kpi_vals = {
            "report_id": report_id,
            "name": config.name,
            "description": config.description,
            "type": config.type,
            "compare_method": config.compare_method,
            "accumulation_method": config.accumulation_method,
            "sequence": config.sequence or 10,
            "auto_expand_accounts": config.show_account_details,
            "style_id": style_id,
        }
        kpi = self._kpi_model.create(kpi_vals)
        self._expression_model.create({"kpi_id": kpi.id, "name": config.expression})
        return kpi

    def _run(
        self,
        name: str,
        description: str | None = None,
        kpis: list[dict[str, Any]] = None,
        default_style: MISStyleConfig | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate MIS report template in Odoo"""
        try:
            # Convert input to MISTemplateConfig
            template_config = MISTemplateConfig(
                name=name,
                description=description,
                kpis=[MISKPIConfig(**kpi) for kpi in (kpis or [])],
                default_style=default_style,
            )

            style_id = None
            if template_config.default_style:
                style_id = self._create_style(template_config.default_style)

            # Create template
            template = self._report_model.create(
                {
                    "name": template_config.name
                    + datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
                    "description": template_config.description,
                    "style_id": style_id,
                }
            )

            # Create KPIs
            for kpi_config in template_config.kpis:
                self._create_kpi(template.id, kpi_config)

            return {
                "success": True,
                "message": f"Successfully created MIS report template '{template_config.name}'",
                "template_id": template.id,
            }

        except Exception as e:
            _logger.error(e)
            return {
                "success": False,
                "message": f"Error creating template: {str(e)}",
                "error_details": {"exception": str(e)},
            }
