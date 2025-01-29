{
    'name': 'LLM Crew Integration',
    'version': '1.0',
    'category': 'Productivity/Intelligence',
    'summary': 'Integrate CrewAI capabilities with Odoo',
    'description': """
        This module integrates CrewAI functionality with Odoo,
        allowing teams to leverage AI agents for task execution
        and collaboration.
        
        Features:
        - Convert users to AI agents
        - Transform teams into AI crews
        - Enable AI task execution
        - Integrate with existing LLM providers
    """,
    'author': 'Apexive',
    'website': 'https://www.apexive.com',
    'depends': [
        'base',
        'mail',
        'sales_team',
        'project',
        'queue_job',
        'llm',  # Base LLM module
    ],
    'data': [
        'security/llm_crew_security.xml',
        'security/ir.model.access.csv',
        'views/res_users_views.xml',
        'views/crm_team_views.xml',
        'views/project_task_views.xml',
    ],
    'external_dependencies': {
        'python': [
            'crewai',
            'langchain_openai',
            'langchain_anthropic',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
