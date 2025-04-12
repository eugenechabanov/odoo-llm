{
    "name": "Website LLM Models",
    "summary": """
        Public website page to display available LLM models""",
    "description": """
        This module adds a public website page that displays 
        all available LLM models in the system, categorized by their use
        and provider. The page is accessible at /llm/models.
    """,
    "author": "Apexive Solutions LLC",
    "website": "https://github.com/apexive/odoo-llm",
    "category": "Website",
    "version": "16.0.1.0.0",
    "depends": ["llm", "website"],
    "data": [
        "security/ir.model.access.csv",
        "views/templates.xml",
        "views/website_menu.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "auto_install": False,
}
