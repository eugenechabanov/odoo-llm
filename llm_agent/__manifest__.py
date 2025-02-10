{
    "name": "LLM Agent",
    "version": "1.0",
    "category": "Project Management",
    "summary": "LLM Agent Integration for Odoo",
    "description": """
        Integrate LLM Agents with Odoo for AI-powered automation
    """,
    "author": "Apexive Solutions LLC",
    "python": ">=3.10.0",
    "depends": [
        "base",
        "project",
        "llm",  # Base LLM module
        "base_accounting_kit",  # For MIS report generation
        "mis_builder",  # For MIS report generation
        "mis_builder_demo",  # For MIS report generation
    ],
    "external_dependencies": {
        "python": ["crewai"],
    },
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
    "images": [
        "static/description/banner.jpeg",
    ],
}
