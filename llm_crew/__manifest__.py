{
    "name": "LLM Crew",
    "version": "1.0",
    "category": "Sales/CRM",
    "summary": "CrewAI Integration for Odoo",
    "description": """
        Integrate CrewAI with Odoo for AI-powered team collaboration
    """,
    "depends": [
        "base",
        "crm",
        "project",
        "llm",  # Base LLM module
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/llm_crew_agent_views.xml",
        "views/crm_team_views.xml",
        "views/project_task_views.xml",
        "views/menu_views.xml",
    ],
    "website": "https://github.com/apexive/odoo-llm",
    "installable": True,
    "application": False,
    "auto_install": False,
}
