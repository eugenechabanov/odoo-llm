{
    'name': 'LLM Agent Base',
    'version': '1.0',
    'category': 'Technical',
    'summary': 'Base module for LLM agent management',
    'description': """
        Base module providing core functionality for managing LLM agents and their tools.
        Includes models and views for agent configuration, team structure, and tool management.
    """,
    'author': 'Apexive Solutions LLC',
    'website': 'https://www.apexive.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'llm',
    ],
    'data': [
        'security/llm_agent_security.xml',
        'security/ir.model.access.csv',
        'views/llm_agent_views.xml',
        'views/llm_agent_tool_views.xml',
        'views/llm_agent_tool_provider_views.xml',
        'views/llm_agent_menus.xml',
    ],
    'installable': True,
    'application': True,
}
