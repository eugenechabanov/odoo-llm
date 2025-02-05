{
    "name": "LLM Agent",
    "version": "1.0",
    "category": "Project Management",
    "summary": "LLM Agent Integration for Odoo",
    "description": """
        Integrate LLM Agents with Odoo for AI-powered automation
    """,
    "depends": [
        "base",
        "project",
        "llm",  # Base LLM module
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/llm_agent_views.xml",
        "views/project_task_views.xml",
        "views/menu_views.xml",
    ],
    "website": "https://github.com/apexive/odoo-llm",
    "installable": True,
    "application": True,
    "auto_install": False,
    "license": "LGPL-3",
}
