{
    "name": "LLM Agent",
    "version": "1.0",
    "category": "Technical",
    "summary": "Module for LLM agent management",
    "description": """
        Module providing functionality for managing LLM agents and their tools.
        Includes models and views for agent configuration, team structure, and tool management.
    """,
    "author": "Apexive Solutions LLC",
    "website": "https://www.apexive.com",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "llm",
    ],
    "data": [
        "security/llm_agent_security.xml",
        "security/ir.model.access.csv",
        "views/llm_agent_views.xml",
        "views/llm_agent_tool_views.xml",
        "views/llm_agent_tool_provider_views.xml",
        "views/menu_views.xml",
    ],
    "installable": True,
    "application": True,
}
