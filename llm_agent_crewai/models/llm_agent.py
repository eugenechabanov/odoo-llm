from odoo import api, models, _
from odoo.exceptions import UserError

from crewai import Agent, LLM
from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

class LLMAgent(models.Model):
    """Extends the base LLM agent model to support CrewAI integration."""
    _inherit = 'llm.agent'

    def _generate_step_message(self, step):
        """Generate formatted message for step callback.

        Args:
            step: AgentAction or AgentFinish object from CrewAI

        Returns:
            string: html_message
        """
        # Extract values with defaults
        thought = getattr(step, "thought", "No thought provided")
        tool = getattr(step, "tool", None)
        tool_input = getattr(step, "tool_input", None)
        output = getattr(step, "output", None)
        result = getattr(step, "result", None)

        # Build HTML message
        html_parts = [
            f"<b>Agent {self.name}:</b><br/>",
            f"<b>Thought:</b> {thought}<br/>",
            f"<b>Tool:</b> {tool}<br/>" if tool else "",
            f"<b>Tool Input:</b> {tool_input}<br/>" if tool_input else "",
            f"<b>Output:</b> {output}"
            if output
            else (f"<b>Result:</b> {result}" if result else str(step)),
        ]
        html_message = "".join(html_parts)

        return html_message

    @api.model
    def _get_available_services(self):
        """Add CrewAI service to available services."""
        services = super()._get_available_services()
        services.append(('crewai', 'CrewAI'))
        return services

    def crewai_get_instance(self, **kwargs):
        """Get a CrewAI Agent instance based on this record.
        
        This method follows the service dispatch pattern from llm.service.mixin.
        The method name is prefixed with 'crewai_' to match the service code.
        
        Returns:
            crewai.Agent: The CrewAI Agent instance configured with this record's settings.
        
        Raises:
            UserError: If required configuration is missing.
        """
        self.ensure_one()

        if not self.llm_model_id:
            raise UserError(_("LLM Model is required for CrewAI agent"))

        if not self.role:
            raise UserError(_("Role is required for CrewAI agent"))

        if not self.goal:
            raise UserError(_("Goal is required for CrewAI agent"))

        # Get tools from the agent's tool_ids
        tools = []
        for tool in self.tool_ids:
            tool_instance = tool.get_instance()
            if tool_instance:
                tools.append(tool_instance)
        content = """
        Comprehensive MIS Builder Module Documentation
Table of Contents
Overview of the MIS Builder Module
Model Definitions and Field Specifications
KPI Expression Syntax
Designing an Ideal PnL Report for a Tech Company
Odoo ORM Call Flow to Generate the PnL Report
Code Examples and Implementation Details
Conclusion and Best Practices
1. Overview of the MIS Builder Module
The MIS Builder module provides a robust framework for generating detailed Management Information System (MIS) reports. It leverages a builder-pattern design to separate concerns into:

Style (mis.report.style):
Handles visual formatting (colors, fonts, margins, etc.).

Report Structure (mis.report):
Defines the blueprint for report sections and includes support for dynamic KPI expressions.

Report Instance (mis.report.instance):
Merges style and structure with actual data to generate a complete report.

The module also supports dynamic KPI expressions using special elements and variables to compute accounting data.

2. Model Definitions and Field Specifications
MISStyleConfig
This configuration defines the style for MIS reports.

Key Fields:

name: Optional style name.
style_id: ID of an existing style.
color: Text color (e.g., "#000000").
background_color: Background color (e.g., "#FFFFFF").
font_style: Options like "normal" or "italic".
font_weight: Options like "normal" or "bold".
font_size: Sizes like "medium", "small", "large", etc.
indent_level: Indentation level (integer, ≥ 0).
prefix: Prefix to add before numbers (e.g., "$").
suffix: Suffix to add after numbers.
dp: Number of decimal places.
divider: Number scaling factor (e.g., "1", "1e3").
hide_empty: Boolean flag to hide empty/zero values.
hide_always: Boolean flag to always hide the element.
MISKPIConfig
This configuration defines an individual KPI in the MIS report.

Key Fields:

name: Technical name of the KPI (must be a valid Python identifier).
description: Human-readable description.
expression: The expression used to compute the KPI.
Examples:
bal[70]: Variation of account 70’s balance.
debp[55%][('journal_id.code', '=', 'BNK1')]: Sum of debits for accounts starting with 55 for journal BNK1.
gross_profit = revenue - expenses: Combining other KPI values.
type: KPI type (num, pct, str).
compare_method: How to compare periods (diff, pct, none).
accumulation_method: How to accumulate over time (sum, avg, none).
sequence: Display order.
show_account_details: Whether to expand account details.
style: Reference to a MISStyleConfig.
MISTemplateConfig
This configuration defines the MIS report template.

Key Fields:

name: Name of the template.
description: Detailed description of the template's purpose.
kpis: List of MISKPIConfig objects.
default_style: A default style to apply to KPIs without a specific style.
3. KPI Expression Syntax
Expressions in the module use special elements to compute accounting data:

Special Elements:

Data Elements:
bal, crd, deb, pbal, nbal, fld
Represent balance, credit, debit, positive balance, negative balance, or other numerical fields.
Period Specifiers:
p: Variation over the period.
i: Initial balance.
e: Ending balance.
Field Specifier:
When using fld, a field name is provided (e.g., fldp.quantity).
Account Selector:
Can be a like expression (e.g., 70%) or a domain (e.g., [('code', 'like', '60%')]).
Journal Items Domain:
An Odoo domain filter on journal items.
Special Case:
balu[]: For unallocated profit/loss of previous fiscal years.
Additional Variables/Functions Available:

Built-in functions: sum, min, max, len, avg
Python modules: datetime, dateutil
Period dates: date_from, date_to
AccountingNone: Behaves as 0 in arithmetic operations.
Example Expressions:

bal[70] or balp[70]: Variation of the balance of account 70 over the period.
bali[70,60]: Initial balance of accounts 70 and 60.
bale[1%]: Ending balance of accounts starting with 1.
crdp[40%]: Sum of credits for accounts starting with 40 during the period.
debp[55%][('journal_id.code', '=', 'BNK1')]: Sum of debits on accounts starting with 55 for journal BNK1.
balp[('user_type_id', '=', ref('account.data_account_type_receivable').id)][]: Variation of receivable accounts’ balance.
pbale[55%]: Sum of ending positive balances for accounts starting with 55.
For liabilities and revenues, use a negative sign (e.g., -balp[...]).
4. Designing an Ideal PnL Report for a Tech Company
An ideal Profit and Loss (PnL) report for a tech company should include:

Revenue
Sources:
Software subscriptions & licensing fees.
Cloud services & maintenance contracts.
Advertising and digital services.
Details:
Gross revenue vs. net revenue after adjustments.
Cost of Goods Sold (COGS)
Direct Costs:
Hosting costs, licensing fees, product development labor, third-party services.
Gross Profit
Calculation:
Gross Profit = Total Revenue – COGS
KPI:
Gross Profit Margin = (Gross Profit / Revenue) × 100
Operating Expenses
Breakdown:
Research & Development (R&D)
Sales & Marketing
General & Administrative (G&A)
Customer support, IT infrastructure (if applicable)
Operating Income
Calculation:
Operating Income = Gross Profit – Operating Expenses
Non-operating Items
Details:
Interest, gains/losses, depreciation/amortization.
Pre-Tax Income and Net Income
Final Metrics:
Net Income = Pre-Tax Income – Taxes
Additional Metrics
EBITDA:
Earnings before interest, taxes, depreciation, and amortization.
Tech-Specific KPIs:
Recurring revenue, Customer Acquisition Cost (CAC), Lifetime Value (LTV), etc.
5. Odoo ORM Call Flow to Generate the PnL Report
Step 1: Retrieve the MIS Report Template
python
Copy
template = self.env['mis.report.template'].search([
    ('name', '=', 'PnL Report Template')
], limit=1)
Step 2: Retrieve Linked KPI Records
python
Copy
kpi_records = template.kpi_ids
Step 3: Query Accounting Data
a. Retrieve Revenue and Expense Accounts:

python
Copy
revenue_accounts = self.env['account.account'].search([
    ('user_type_id.type', '=', 'revenue'),
    ('company_id', '=', company_id)
])
expense_accounts = self.env['account.account'].search([
    ('user_type_id.type', '=', 'expense'),
    ('company_id', '=', company_id)
])
b. Aggregate Data with read_group:

python
Copy
revenue_data = self.env['account.move.line'].read_group(
    domain=[
        ('account_id', 'in', revenue_accounts.ids),
        ('move_id.state', '=', 'posted'),
        ('date', '>=', date_from),
        ('date', '<=', date_to)
    ],
    fields=['balance:sum'],
    groupby=[]
)
total_revenue = revenue_data[0].get('balance') if revenue_data else 0

expense_data = self.env['account.move.line'].read_group(
    domain=[
        ('account_id', 'in', expense_accounts.ids),
        ('move_id.state', '=', 'posted'),
        ('date', '>=', date_from),
        ('date', '<=', date_to)
    ],
    fields=['balance:sum'],
    groupby=[]
)
total_expenses = expense_data[0].get('balance') if expense_data else 0
Step 4: Build the Data Context for KPI Evaluation
python
Copy
data_context = {
    'total_revenue': total_revenue,
    'total_expenses': total_expenses,
    'balp': {
        '70': total_revenue,  # Example mapping for revenue
        '80': total_expenses, # Example mapping for expenses
    },
    'date_from': date_from,
    'date_to': date_to,
}
Step 5: Evaluate KPI Expressions
python
Copy
from odoo.tools.safe_eval import safe_eval

results = {}
for kpi in kpi_records:
    try:
        eval_context = {'balp': data_context['balp'], **data_context}
        result = safe_eval(kpi.expression, eval_context)
        results[kpi.name] = result
    except Exception as e:
        results[kpi.name] = f"Error: {str(e)}"
Step 6: Render and Generate the Report
Prepare Report Data:
python
Copy
report_data = {
    'template': template,
    'kpi_results': results,
    'style': template.style_id or default_style,
}
Render Using QWeb (Example Snippet):
xml
Copy
<t t-name="mis_report.report_template">
  <div style="color: <t t-esc="style.color"/>; font-size: <t t-esc="style.font_size"/>;">
    <h2><t t-esc="template.name"/></h2>
    <div>
      <t t-foreach="template.kpi_ids" t-as="kpi">
        <div>
          <strong><t t-esc="kpi.description"/></strong>:
          <span><t t-esc="kpi_results.get(kpi.name, 'N/A')"/></span>
        </div>
      </t>
    </div>
  </div>
</t>
Export as PDF:
python
Copy
return self.env.ref('mis_report.action_report_pdf').report_action(template, data=report_data)
6. Code Examples and Implementation Details
Example: Model Definitions
python
Copy
from odoo import models, fields, api
from odoo.tools.safe_eval import safe_eval

class MISReportStyle(models.Model):
    _name = 'mis.report.style'
    _description = 'MIS Report Style'
    
    name = fields.Char(string='Style Name')
    color = fields.Char(string='Text Color', default="#000000")
    background_color = fields.Char(string='Background Color', default="#FFFFFF")
    font_style = fields.Selection([('normal', 'Normal'), ('italic', 'Italic')], default='normal')
    font_weight = fields.Selection([('normal', 'Normal'), ('bold', 'Bold')], default='normal')
    font_size = fields.Selection([
        ('xx-small', 'Extra Extra Small'),
        ('x-small', 'Extra Small'),
        ('small', 'Small'),
        ('medium', 'Medium'),
        ('large', 'Large'),
        ('x-large', 'Extra Large'),
        ('xx-large', 'Extra Extra Large'),
    ], default='medium')
    indent_level = fields.Integer(string='Indentation Level', default=0)
    prefix = fields.Char(string='Number Prefix')
    suffix = fields.Char(string='Number Suffix')
    dp = fields.Integer(string='Decimal Places', default=2)
    divider = fields.Char(string='Divider', default="1")
    hide_empty = fields.Boolean(string='Hide Empty', default=False)
    hide_always = fields.Boolean(string='Always Hide', default=False)


class MISReportKPI(models.Model):
    _name = 'mis.report.kpi'
    _description = 'MIS Report KPI'
    
    name = fields.Char(string='KPI Technical Name', required=True)
    description = fields.Char(string='KPI Description', required=True)
    expression = fields.Text(string='KPI Expression', required=True)
    kpi_type = fields.Selection([('num', 'Numeric'), ('pct', 'Percentage'), ('str', 'String')],
                                string='KPI Type', default='num')
    compare_method = fields.Selection([('diff', 'Difference'), ('pct', 'Percentage'), ('none', 'None')],
                                      string='Comparison Method', default='pct')
    accumulation_method = fields.Selection([('sum', 'Sum'), ('avg', 'Average'), ('none', 'None')],
                                           string='Accumulation Method', default='sum')
    sequence = fields.Integer(string='Sequence', default=10)
    show_account_details = fields.Boolean(string='Show Account Details', default=False)
    style_id = fields.Many2one('mis.report.style', string='Style')
    template_id = fields.Many2one('mis.report.template', string='Template')


class MISReportTemplate(models.Model):
    _name = 'mis.report.template'
    _description = 'MIS Report Template'
    
    name = fields.Char(string='Template Name', required=True)
    description = fields.Text(string='Description')
    kpi_ids = fields.One2many('mis.report.kpi', 'template_id', string='KPIs')
    style_id = fields.Many2one('mis.report.style', string='Default Style')
Example: Evaluating and Rendering the Report
python
Copy
class MISReportTemplate(models.Model):
    _inherit = 'mis.report.template'

    @api.model
    def generate_report(self, date_from, date_to, company_id):
        # Retrieve KPI records
        template = self.search([('name', '=', 'PnL Report Template')], limit=1)
        kpi_records = template.kpi_ids
        
        # Query revenue and expense accounts
        revenue_accounts = self.env['account.account'].search([
            ('user_type_id.type', '=', 'revenue'),
            ('company_id', '=', company_id)
        ])
        expense_accounts = self.env['account.account'].search([
            ('user_type_id.type', '=', 'expense'),
            ('company_id', '=', company_id)
        ])
        
        # Aggregate data using read_group
        revenue_data = self.env['account.move.line'].read_group(
            domain=[
                ('account_id', 'in', revenue_accounts.ids),
                ('move_id.state', '=', 'posted'),
                ('date', '>=', date_from),
                ('date', '<=', date_to)
            ],
            fields=['balance:sum'],
            groupby=[]
        )
        total_revenue = revenue_data[0].get('balance') if revenue_data else 0
        
        expense_data = self.env['account.move.line'].read_group(
            domain=[
                ('account_id', 'in', expense_accounts.ids),
                ('move_id.state', '=', 'posted'),
                ('date', '>=', date_from),
                ('date', '<=', date_to)
            ],
            fields=['balance:sum'],
            groupby=[]
        )
        total_expenses = expense_data[0].get('balance') if expense_data else 0
        
        # Build evaluation context
        data_context = {
            'total_revenue': total_revenue,
            'total_expenses': total_expenses,
            'balp': {
                '70': total_revenue,
                '80': total_expenses,
            },
            'date_from': date_from,
            'date_to': date_to,
        }
        
        # Evaluate KPI expressions
        results = {}
        for kpi in kpi_records:
            try:
                eval_context = {'balp': data_context['balp'], **data_context}
                result = safe_eval(kpi.expression, eval_context)
                results[kpi.name] = result
            except Exception as e:
                results[kpi.name] = f"Error: {str(e)}"
        
        # Prepare report data for rendering
        report_data = {
            'template': template,
            'kpi_results': results,
            'style': template.style_id,
        }
        
        # Render and export PDF (example using QWeb)
        return self.env.ref('mis_report.action_report_pdf').report_action(template, data=report_data)
7. Conclusion and Best Practices
Comprehensive Data:
The ideal PnL report aggregates detailed revenue and expense information, calculates core metrics like gross profit, and derives additional KPIs (such as margins and EBITDA).

Dynamic Expressions:
Leverage the special syntax (bal, crd, deb, etc.) to build flexible KPI expressions that can reference account data, other KPIs, and perform arithmetic operations.

Styling and Presentation:
Use MISStyleConfig to ensure consistent presentation across the report. Integrate these styles within QWeb templates to generate a professional PDF output.

Extensibility:
This framework is designed to be extended—additional KPIs, more granular account filtering, and custom styling options can be added as needed.


        """
        string_kb = StringKnowledgeSource(
            content=content
        )
        # Create the CrewAI agent with our configuration
        agent = Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory or "",
            allow_delegation=self.is_manager,
            tools=tools,
            verbose=True,
            llm=LLM(
                temperature=0.5,
                model=self.llm_model_id.name,
                api_key=self.llm_model_id.provider_id.api_key,
                base_url=self.llm_model_id.provider_id.api_base,
            ),
            step_callback=lambda step: (
                self.message_post(
                    body=self._generate_step_message(step),
                    message_type="comment",
                    author_id=self.user_id.partner_id.id,
                )
            ),
            knowledge_sources=[string_kb],
        )
        
        return agent
