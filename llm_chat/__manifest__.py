{
    "name": "LLM Chat",
    "version": "1.0",
    "category": "Productivity/LLM",
    "summary": "Chat with AI agents via mentions",
    "description": """
        Enable AI agents to respond to chat mentions in Odoo.
        Tag an AI agent in any chatter to get intelligent responses.
    """,
    "author": "Apexive",
    "depends": [
        "base",
        "mail",
        "llm",
        "llm_crew",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/mail_thread_views.xml",
    ],
    "website": "https://github.com/apexive/odoo-llm",
    "demo": [],
    "installable": True,
    "auto_install": False,
    "application": False,
    "license": "LGPL-3",
}
