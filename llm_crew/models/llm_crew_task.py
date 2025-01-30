from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools.translate import _

class LLMCrewTask(models.Model):
    _name = 'llm.crew.task'
    _description = 'LLM Crew Task'
    _inherit = ['mail.thread']

    name = fields.Char(required=True)
    task_id = fields.Many2one('project.task', string="Related Task", required=True)
    agent_id = fields.Many2one('llm.crew.agent', string="Assigned Agent", required=True)
    crew_id = fields.Many2one(
        'llm.crew.team',
        string="Crew",
        required=True,
        domain="[('project_id', '=', project_id)]"
    )
    project_id = fields.Many2one(
        'project.project',
        related='task_id.project_id',
        store=True,
        readonly=True
    )
    
    # Task Configuration
    description = fields.Text(required=True, help="Task description for the AI agent")
    expected_output = fields.Text(required=True, help="Description of the expected output")
    context = fields.Text(help="Additional context for the task")
    
    output_format = fields.Selection([
        ('text', 'Text'),
        ('json', 'JSON'),
        ('markdown', 'Markdown')
    ], default='text', required=True)
    
    async_execution = fields.Boolean(default=False)
    tools = fields.Text(help="JSON configuration for task-specific tools")
    
    # Execution State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ], default='draft', tracking=True)
    
    result = fields.Text(readonly=True)
    error = fields.Text(readonly=True)
    execution_time = fields.Float(readonly=True)

    _sql_constraints = [
        ('unique_task',
         'unique(task_id)',
         'This task is already configured as an AI task!')
    ]

    @api.onchange('task_id')
    def _onchange_task_id(self):
        """Reset crew when task changes to ensure project match"""
        self.crew_id = False

    def _to_crew_task(self):
        """Convert to CrewAI Task instance"""
        self.ensure_one()
        
        if not self.agent_id:
            raise UserError(_("Task must have an assigned agent"))
            
        from crewai import Task
        return Task(
            description=self.description,
            expected_output=self.expected_output,
            agent=self.agent_id._to_crew_agent(),
            async_execution=self.async_execution,
            output_format=self.output_format,
            context=self.context,
            tools=self.tools and json.loads(self.tools) or None
        )

    def _update_from_result(self, result):
        """Update task from CrewAI execution result"""
        self.write({
            'result': result.raw_output,
            'state': 'completed',
            'execution_time': result.execution_time
        })
