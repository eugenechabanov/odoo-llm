from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class CRMTeam(models.Model):
    _inherit = 'crm.team'

    # Relations
    llm_crew_team_id = fields.Many2one(
        'llm.crew.team',
        string="AI Crew",
        ondelete='cascade'
    )
    
    # Computed Fields
    is_ai_crew = fields.Boolean(
        string="Is AI Crew",
        compute='_compute_is_ai_crew',
        store=True,
        help="Whether this team is configured as an AI crew"
    )

    @api.depends('llm_crew_team_id')
    def _compute_is_ai_crew(self):
        """Compute whether team is configured as AI crew"""
        for team in self:
            team.is_ai_crew = bool(team.llm_crew_team_id)

    def _search_is_ai_crew(self, operator, value):
        """Search teams that are configured as AI crews"""
        if operator not in ('=', '!='):
            raise ValueError(_("Invalid operator for is_ai_crew search"))
            
        crews = self.env['llm.crew.team'].search([('id', '!=', False)])
        team_ids = crews.mapped('team_id').ids
        
        if operator == '=':
            return [('id', 'in' if value else 'not in', team_ids)]
        else:
            return [('id', 'not in' if value else 'in', team_ids)]

    def _to_crew_team(self):
        """Convert to CrewAI Team if AI crew is configured"""
        self.ensure_one()
        if not self.llm_crew_team_id:
            return None
        return self.llm_crew_team_id._to_crew_team()

    def _get_crew_agents(self):
        """Get all AI agents in the crew.
        
        Returns:
            list: List of CrewAI agent instances
        """
        agents = self.member_ids.mapped('crew_agent_id').filtered('llm_enabled')
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
            task._to_crewai_task()
            for task in self.llm_task_ids.filtered(
                lambda t: t.llm_enabled and t.llm_execution_state == 'draft'
            )
            if task._to_crewai_task()  # Filter out None results
        ]

    def _create_crewai_crew(self, agents=None):
        """Create a CrewAI crew instance."""
        from crewai import Crew
        
        # Get agents
        if agents is None:
            agents = []
            for member in self.member_ids:
                if member.llm_enabled:
                    agent = member._create_crewai_agent()
                    if agent:
                        agents.append(agent)
                        
        if not agents:
            raise UserError(_("No AI agents available in the crew"))
            
        config = {
            'agents': agents,
            'tasks': [],  # Tasks will be added during execution
            'process': self.llm_crew_team_id.llm_process or 'sequential',
            'memory': self.llm_crew_team_id.llm_memory_enabled,
        }
        
        # Add manager for hierarchical process
        if self.llm_crew_team_id.llm_process == 'hierarchical' and self.llm_crew_team_id.llm_manager_id:
            config['manager_llm'] = self.llm_crew_team_id.llm_manager_id._get_llm()
            
        return Crew(**config)

    def execute_crew(self):
        """Execute crew tasks."""
        def execute():
            crew = self._create_crewai_crew()
            return crew.kickoff()
            
        return self._execute_llm(execute)
        
    def _execute_crew_background(self, crew):
        """Background execution is not implemented."""
        raise NotImplementedError("Background execution is not supported")

    def _process_crew_result(self, result):
        """Process crew execution result.
        
        Args:
            result: Result from crew.kickoff()
        """
        # Post result as a message
        self.message_post(
            body=_("Crew execution completed with result:\n%s") % result
        )

    @api.onchange('llm_crew_team_id.llm_process')
    def _onchange_llm_process(self):
        """Clear manager when process changes from hierarchical"""
        if self.llm_crew_team_id.llm_process != 'hierarchical':
            self.llm_crew_team_id.llm_manager_id = False
