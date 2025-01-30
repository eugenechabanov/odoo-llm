from odoo import api, fields, models, _
from odoo.exceptions import UserError
import json


class ProjectTask(models.Model):
    _inherit = 'project.task'

    llm_crew_task_id = fields.Many2one('llm.crew.task', string="AI Task")

    @api.depends('llm_crew_task_id')
    def _compute_is_ai_task(self):
        """Compute whether task is configured as AI task"""
        for task in self:
            task.is_ai_task = bool(task.llm_crew_task_id)

    def _to_crew_task(self):
        """Convert to CrewAI Task if AI task is configured"""
        self.ensure_one()
        if not self.llm_crew_task_id:
            return None
        return self.llm_crew_task_id._to_crew_task()

    @api.onchange('llm_enabled')
    def _onchange_llm_enabled(self):
        """Ensure assignee is an AI agent if task is LLM-enabled"""
        if self.llm_enabled and self.user_id and not self.user_id.crew_agent_id.llm_enabled:
            self.user_id = False

    @api.constrains('llm_enabled', 'user_id')
    def _check_llm_assignee(self):
        """Ensure assignee is an AI agent if task is LLM-enabled"""
        for task in self:
            if task.llm_enabled and task.user_id and not task.user_id.crew_agent_id.llm_enabled:
                raise UserError(_(
                    "Task assignee must be an AI agent when LLM is enabled"
                ))

    def _create_crewai_task(self):
        """Create CrewAI task instance.
        
        Returns:
            crewai.Task: Configured CrewAI task instance
            
        Raises:
            UserError: If required fields are not set
        """
        self.ensure_one()
        
        if not self.user_id:
            raise UserError(_("Task must be assigned to an AI agent"))

        agent = self.user_id._create_crewai_agent()
        if not agent:
            raise UserError(_("Task assignee must be an AI agent"))

        from crewai import Task

        # Build task description
        description = self.description or ''
        if self.llm_context:
            description = f"{description}\n\nContext:\n{self.llm_context}"

        config = {
            'description': description,
            'expected_output': self.llm_expected_output,
            'agent': agent,
            'async_execution': self.llm_async_execution,
            'output_format': self.llm_output_format,
        }

        # Add tools if configured
        if self.llm_tools:
            try:
                tools = json.loads(self.llm_tools)
                if tools:
                    config['tools'] = tools
            except json.JSONDecodeError:
                pass  # Invalid JSON, ignore tools

        return Task(**config)

    def execute_task(self):
        """Execute task using LLM."""
        def execute():
            task = self._create_crewai_task()
            return task.execute()
            
        return self._execute_llm(execute)

    def _execute_task_background(self, task):
        """Background execution is not implemented."""
        raise NotImplementedError("Background execution is not supported")
