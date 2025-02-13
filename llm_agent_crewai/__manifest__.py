{
    'name': 'LLM Agent CrewAI',
    'version': '1.0',
    'category': 'Technical',
    'summary': 'CrewAI integration for LLM agents',
    'description': """
        Extends the base LLM agent functionality with CrewAI integration.
        Allows creating and managing CrewAI agents within Odoo.
    """,
    'author': 'Apexive Solutions LLC',
    'website': 'https://www.apexive.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'llm_agent_base',
    ],
    'external_dependencies': {
        'python': ['crewai'],
    },
    'installable': True,
    'application': False,
}
