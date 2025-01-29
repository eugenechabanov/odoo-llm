from odoo import api, fields, models, _
from odoo.exceptions import UserError


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

    def _create_crewai_crew(self, agents):
        """Create CrewAI crew instance.
        
        Args:
            agents: List of CrewAI agent instances
            
        Returns:
            crewai.Crew: Configured CrewAI crew instance
        """
        from crewai import Crew

        config = {
            'agents': agents,
            'tasks': self._get_crew_tasks(),
            'process': self.llm_process,
            'memory': self.llm_memory_enabled,
        }

        # Add manager for hierarchical process
        if self.llm_process == 'hierarchical' and self.llm_manager_id:
            config['manager_llm'] = self.llm_manager_id._get_crewai_llm()

        return Crew(**config)

    def execute_crew(self):
        """Queue crew execution in background."""
        self.ensure_one()
        if not self.llm_enabled:
            raise UserError(_("This team is not LLM-enabled"))

        if self.llm_execution_state != 'draft':
            raise UserError(_("Can only execute crews in draft state"))

        self.llm_execution_state = 'in_progress'
        self.with_delay(channel='llm')._execute_crew_job()

    def _execute_crew_job(self):
        """Background job for crew execution."""
        try:
            crew = self._to_crewai_crew()
            result = crew.kickoff()
            self._process_crew_result(result)
            self.llm_execution_state = 'completed'
        except Exception as e:
            self._handle_execution_error(e)

    def _process_crew_result(self, result):
        """Process crew execution result.
        
        Args:
            result: Result from crew.kickoff()
        """
        # Post result as a message
        self.message_post(
            body=_("Crew execution completed with result:\n%s") % result
        )
