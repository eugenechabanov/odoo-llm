{
    'name': 'LLM Agent CrewAI Project Integration',
    'version': '1.0',
    'category': 'Project',
    'summary': 'Integrate CrewAI agents with project tasks',
    'description': '''
        This module integrates CrewAI agents with project tasks, allowing:
        - Sequential task execution with assigned agents
        - Hierarchical task execution with manager agents
        - AI task execution tracking and results
    ''',
    'author': 'Apexive',
    'website': 'https://www.apexive.com',
    'depends': [
        'project',
        'llm_agent_crewai',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/project_task_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
