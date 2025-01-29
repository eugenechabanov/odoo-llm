from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class CRMTeam(models.Model):
    _inherit = ['crm.team', 'llm.capability.mixin']

    llm_process = fields.Selection([
        ('sequential', 'Sequential'),
        ('hierarchical', 'Hierarchical')
    ], string="Process Type",
        default='sequential',
        help="How agents in the crew work together"
    )
    llm_manager_id = fields.Many2one(
        'res.users',
        string="Manager Agent",
        domain="[('llm_enabled', '=', True)]",
        help="Manager agent for hierarchical process"
    )
    llm_task_ids = fields.One2many(
        'project.task',
        'team_id',
        string="Crew Tasks",
        domain="[('llm_enabled', '=', True)]"
    )

    @api.onchange('llm_process')
    def _onchange_llm_process(self):
        """Clear manager when process changes from hierarchical"""
        if self.llm_process != 'hierarchical':
            self.llm_manager_id = False

    def _get_crew_agents(self):
        """Get all AI agents in the crew.
        
        Returns:
            list: List of CrewAI agent instances
        """
        return [
            member._to_crewai_agent()
            for member in self.member_ids.filtered('llm_enabled')
            if member._to_crewai_agent()  # Filter out None results
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

    def _to_crewai_crew(self):
        """Convert to CrewAI Crew if LLM enabled.
        
        Returns:
            crewai.Crew: CrewAI crew instance if LLM enabled, None otherwise
            
        Raises:
            UserError: If no AI agents configured
        """
        self.ensure_one()
        if not self.llm_enabled:
            return None

        agents = self._get_crew_agents()
        if not agents:
            raise UserError(_("No AI agents configured in crew %s") % self.name)

        return self._create_crewai_crew(agents)

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
            'process': self.llm_process or 'sequential',
            'memory': self.llm_memory_enabled,
        }
        
        # Add manager for hierarchical process
        if self.llm_process == 'hierarchical' and self.llm_manager_id:
            config['manager_llm'] = self.llm_manager_id._get_llm()
            
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
