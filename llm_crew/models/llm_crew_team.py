from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class LLMCrewTeam(models.Model):
    """Team LLM capabilities and configuration."""
    _name = 'llm.crew.team'
    _description = 'LLM Crew Team'
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
    
    # Process Configuration
    process = fields.Selection([
        ('sequential', 'Sequential'),
        ('hierarchical', 'Hierarchical')
    ], string="Process Type",
        default='sequential',
        help="How agents in the crew work together"
    )
    manager_id = fields.Many2one(
        'res.users',
        string="Manager Agent",
        domain="[('crew_agent_id.llm_enabled', '=', True)]",
        help="Manager agent for hierarchical process"
    )
    task_ids = fields.One2many(
        'project.task',
        'team_id',
        string="Crew Tasks",
        domain="[('llm_enabled', '=', True)]"
    )

    _sql_constraints = [
        ('unique_team',
         'unique(team_id)',
         'LLM configuration already exists for this team!')
    ]

    @api.onchange('process')
    def _onchange_process(self):
        """Clear manager when process changes from hierarchical"""
        if self.process != 'hierarchical':
            self.manager_id = False

    def _get_crew_agents(self):
        """Get all AI agents in the crew.
        
        Returns:
            list: List of CrewAI agent instances
        """
        agents = self.team_id.member_ids.mapped('crew_agent_id').filtered('llm_enabled')
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
        return [
            task._create_crewai_task()
            for task in self.task_ids.filtered('llm_enabled')
            if task.stage_id.is_closed is False  # Only active tasks
        ]

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
