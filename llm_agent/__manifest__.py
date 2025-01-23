{
    'name': 'LLM Agent',
    'version': '1.0',
    'category': 'Productivity/Discuss',
    'summary': 'AI Agents powered by LLM',
    'description': """
        Create and manage AI agents powered by LLM models.
        Agents can interact with users through Odoo's chat interface.
    """,
    'depends': [
        'base',
        'mail',
        'llm',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/agent_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
