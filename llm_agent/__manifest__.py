{
    "name": "LLM Agent",
    "version": "1.0",
    "category": "Productivity/Discuss",
    "summary": "LLM Agents powered by language models",
    "description": """
        Create and manage LLM agents powered by language models.
        Agents can interact with users through Odoo's chat interface.
    """,
    "depends": [
        "base",
        "mail",
        "llm",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/agent_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
    "images": [
        "static/description/banner.jpeg",
    ],
}
