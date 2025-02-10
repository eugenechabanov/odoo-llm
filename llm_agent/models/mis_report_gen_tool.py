from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

class MISPeriodConfig(BaseModel):
    """Configuration for a period in MIS report instance"""
    name: str = Field(
        ..., 
        description="Label for the period"
    )
    mode: str = Field(
        default="fix",
        description="""
        Mode for date selection:
        - fix: Fixed dates
        - relative: Relative to report base date
        - none: No date filter
        """
    )
    source: str = Field(
        default="actuals",
        description="""
        Source of data:
        - actuals: Current data from accounting
        - actuals_alt: Alternative source
        - sumcol: Sum of other columns
        - cmpcol: Compare columns
        """
    )
    date_from: Optional[str] = Field(
        None,
        description="Start date for fixed period (YYYY-MM-DD)"
    )
    date_to: Optional[str] = Field(
        None,
        description="End date for fixed period (YYYY-MM-DD)" 
    )
    offset: Optional[int] = Field(
        None,
        description="Offset from current period for relative mode"
    )
    duration: Optional[int] = Field(
        None,
        description="Number of periods for relative mode"
    )
    type: Optional[str] = Field(
        None,
        description="""
        Period type for relative mode:
        - d: Day
        - w: Week 
        - m: Month
        - y: Year
        - date_range: Date Range
        """
    )

class MISInstanceConfig(BaseModel):
    """Configuration for MIS report instance"""
    name: str = Field(
        ...,
        description="Name of the report instance"
    )
    template_id: int = Field(
        ...,
        description="ID of the MIS report template to use"
    )
    date: Optional[str] = Field(
        None,
        description="Base date for the report (YYYY-MM-DD)"
    )
    target_move: str = Field(
        default="posted",
        description="""
        Target moves to include:
        - posted: All Posted Entries
        - all: All Entries
        """
    )
    company_id: Optional[int] = Field(
        None,
        description="Company ID (leave empty for multi-company)"
    )
    multi_company: bool = Field(
        default=False,
        description="Enable multi-company mode"
    )
    company_ids: Optional[List[int]] = Field(
        None,
        description="List of company IDs for multi-company mode"
    )
    currency_id: Optional[int] = Field(
        None,
        description="Currency ID for the report"
    )
    periods: List[MISPeriodConfig] = Field(
        ...,
        description="List of periods to include in the report"
    )
    analytic_domain: str = Field(
        default="[]",
        description="Domain to filter analytic entries"
    )

class MISReportInstanceGenTool(BaseTool):
    """Tool to generate MIS report instances"""
    name: str = "MIS Report Instance Generator"
    description: str = """
    Creates Management Information System (MIS) report instances in Odoo.
    This tool generates report instances from templates with configured periods.
    
    The tool can:
    1. Create report instances with multiple periods
    2. Configure date ranges (fixed or relative)
    3. Set up data sources (actuals, comparisons, sums)
    4. Handle multi-company scenarios
    5. Apply analytic filters
    
    Required:
    1. Template ID
    2. Instance name
    3. Period configurations with following fields:
       
       name: str (required)
       - Label for the period (e.g., "Q1 2024", "Last Year")
       
       mode: str (default="fix")
       - fix: Use fixed start and end dates
       - relative: Calculate dates relative to report base date
       - none: No date filter
       
       source: str (default="actuals")
       - actuals: Current data from accounting move lines
       - actuals_alt: Data from alternative move line source
       - sumcol: Sum of other columns
       - cmpcol: Compare columns
       
       date_from: str (optional)
       - Start date for fixed mode (YYYY-MM-DD)
       - Required if mode='fix'
       
       date_to: str (optional)
       - End date for fixed mode (YYYY-MM-DD)
       - Required if mode='fix'
       
       type: str (optional)
       - Period type for relative mode:
         * d: Day
         * w: Week
         * m: Month
         * y: Year
         * date_range: Date Range
       - Required if mode='relative'
       
       offset: int (optional)
       - Offset from current period for relative mode
       - Example: -1 for previous period, 1 for next period
       - Required if mode='relative'
       
       duration: int (optional)
       - Number of periods to include
       - Example: 1 for single period, 3 for quarter
       - Required if mode='relative'
       
    Example Usage:
    {
        "name": "Q1 2024 P&L",
        "template_id": 1,
        "date": "2024-01-01",
        "periods": [
            {
                "name": "Q1 2024",
                "mode": "fix",
                "source": "actuals",
                "date_from": "2024-01-01",
                "date_to": "2024-03-31"
            },
            {
                "name": "Q1 2023",
                "mode": "fix",
                "source": "actuals", 
                "date_from": "2023-01-01",
                "date_to": "2023-03-31"
            }
        ]
    }
    """
    args_schema: Type[BaseModel] = MISInstanceConfig

    def __init__(self, env: Any, **kwargs: Any) -> None:
        """Initialize with Odoo environment"""
        super().__init__(**kwargs)
        self._env = env

    def _run(
        self,
        name: str,
        template_id: int,
        periods: List[Dict[str, Any]],
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Generate MIS report instance"""
        try:
            # Create instance
            instance_vals = {
                'name': name,
                'report_id': template_id,
                'target_move': kwargs.get('target_move', 'posted'),
                'multi_company': kwargs.get('multi_company', False),
                'analytic_domain': kwargs.get('analytic_domain', '[]'),
            }
            
            if kwargs.get('date'):
                instance_vals['date'] = kwargs['date']
            
            if kwargs.get('company_id'):
                instance_vals['company_id'] = kwargs['company_id']
                
            if kwargs.get('company_ids'):
                instance_vals['company_ids'] = [(6, 0, kwargs['company_ids'])]
                
            if kwargs.get('currency_id'):
                instance_vals['currency_id'] = kwargs['currency_id']
                
            instance = self._env['mis.report.instance'].create(instance_vals)
            
            # Create periods
            for period in periods:
                period_vals = {
                    'name': period['name'],
                    'report_instance_id': instance.id,
                    'mode': period['mode'],
                    'source': period['source'],
                }
                
                if period['mode'] == 'fix':
                    period_vals.update({
                        'manual_date_from': period['date_from'],
                        'manual_date_to': period['date_to'],
                    })
                elif period['mode'] == 'relative':
                    period_vals.update({
                        'type': period['type'],
                        'offset': period['offset'],
                        'duration': period['duration'],
                    })
                    
                self._env['mis.report.instance.period'].create(period_vals)
                
            return {
                'success': True,
                'message': f"Successfully created MIS report instance '{name}'",
                'instance_id': instance.id
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f"Error creating instance: {str(e)}",
                'error_details': {'exception': str(e)}
            }