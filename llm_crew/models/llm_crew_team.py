from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class LLMCrewTeam(models.Model):
    """Team LLM capabilities and configuration."""
    _name = 'llm.crew.team'
    _description = 'LLM Crew Team Configuration'
    _inherit = ['llm.capability.mixin']

    name = fields.Char(related='team_id.name', store=True, readonly=True)
    active = fields.Boolean(default=True)
    
    # Relations
    team_id = fields.Many2one(
        'crm.team',
        string="Sales Team",
        required=True,
        ondelete='cascade',
        index=True
    )
    project_id = fields.Many2one(
        'project.project',
        string="Project",
        required=True,
        ondelete='cascade',
        index=True,
        help="Project this crew is working on"
    )
    task_ids = fields.One2many(
        'llm.crew.task',
        'crew_id',
        string="Tasks",
        help="AI tasks assigned to this crew"
    )
    
    # Process Configuration
    process = fields.Selection([
        ('sequential', 'Sequential'),
        ('hierarchical', 'Hierarchical')
    ], string="Process Type",
        default='sequential',
        required=True,
        help="How agents in the crew work together"
    )
    manager_id = fields.Many2one(
        'res.users',
        string="Manager Agent",
        domain="[('is_ai_agent', '=', True)]",
        help="Manager agent for hierarchical process"
    )

    _sql_constraints = [
        ('unique_team',
         'unique(team_id)',
         'LLM configuration already exists for this team!'),
        ('unique_project_team',
         'unique(project_id, team_id)',
         'This team is already assigned to this project!')
    ]

    @api.onchange('process')
    def _onchange_process(self):
        """Reset manager when process type changes."""
        if self.process != 'hierarchical':
            self.manager_id = False

    def _get_crew_agents(self):
        """Get all AI agents in the crew.
        
        Returns:
            list: List of CrewAI agent instances
        """
        agents = self.team_id.member_ids.mapped('llm_crew_agent_id').filtered('llm_enabled')
        return [
            agent._to_crewai_agent()
            for agent in agents
            if agent  # Filter out empty records
        ]

    def _get_crew_tasks(self):
        """Get all active AI tasks for the crew.
        
        Returns:
            list: List of CrewAI task instances
        """
        self.ensure_one()
        tasks = self.task_ids.filtered(lambda t: not t.task_id.stage_id.is_closed)
        return [task._to_crew_task() for task in tasks]

    def _to_crewai_crew(self):
        """Convert to CrewAI Crew instance.
        
        Returns:
            crewai.Crew: CrewAI crew instance
            
        Raises:
            UserError: If required configuration is missing
        """
        self.ensure_one()
        
        if not self.llm_enabled:
            raise UserError(_("LLM capabilities not enabled for team %s") % self.name)
            
        agents = self._get_crew_agents()
        if not agents:
            raise UserError(_("No AI agents configured for team %s") % self.name)
            
        tasks = self._get_crew_tasks()
        if not tasks:
            raise UserError(_("No active tasks found for team %s") % self.name)

        from crewai import Crew
        return Crew(
            agents=agents,
            tasks=tasks,
            process=self.process,
            manager=self.manager_id._to_crewai_agent() if self.process == 'hierarchical' else None
        )    
