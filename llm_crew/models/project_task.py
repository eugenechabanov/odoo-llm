from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class ProjectTask(models.Model):
    _inherit = ['project.task', 'llm.capability.mixin']

    llm_expected_output = fields.Text(
        string="Expected Output",
        help="Description of the expected output from this task"
    )
    llm_output_format = fields.Selection([
        ('text', 'Text'),
        ('json', 'JSON'),
        ('markdown', 'Markdown')
    ], string="Output Format",
        default='text',
        help="Format of the task output"
    )
    llm_async_execution = fields.Boolean(
        string="Async Execution",
        default=False,
        help="Execute this task asynchronously"
    )
    llm_result = fields.Text(
        string="LLM Result",
        readonly=True,
        help="Result from LLM task execution"
    )
    llm_context = fields.Text(
        string="Task Context",
        help="Additional context for the task"
    )
    llm_tools = fields.Text(
        string="Task Tools",
        help="JSON configuration for task-specific tools"
    )

    @api.onchange('llm_enabled')
    def _onchange_llm_enabled(self):
        """Ensure assignee is an AI agent if task is LLM-enabled"""
        if self.llm_enabled and self.user_id and not self.user_id.llm_enabled:
            self.user_id = False

    @api.constrains('llm_enabled', 'user_id')
    def _check_llm_assignee(self):
        """Ensure assignee is an AI agent if task is LLM-enabled"""
        for task in self:
            if task.llm_enabled and task.user_id and not task.user_id.llm_enabled:
                raise UserError(_(
                    "Task assignee must be an AI agent when LLM is enabled"
                ))

    def _to_crewai_task(self):
        """Convert to CrewAI Task if LLM enabled.
        
        Returns:
            crewai.Task: CrewAI task instance if LLM enabled, None otherwise
            
        Raises:
            UserError: If required fields are not set
        """
        self.ensure_one()
        if not self.llm_enabled:
            return None

        if not self.user_id:
            raise UserError(_("Task must be assigned to an AI agent"))

        agent = self.user_id._to_crewai_agent()
        if not agent:
            raise UserError(_("Task assignee must be an AI agent"))

        return self._create_crewai_task(agent)

    def _create_crewai_task(self, agent):
        """Create CrewAI task instance.
        
        Args:
            agent: CrewAI agent instance
            
        Returns:
            crewai.Task: Configured CrewAI task instance
        """
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
            import json
            try:
                tools = json.loads(self.llm_tools)
                if tools:
                    config['tools'] = tools
            except json.JSONDecodeError:
                pass  # Invalid JSON, ignore tools

        return Task(**config)

    def execute_task(self):
        """Execute task using LLM.
        
        If async execution is enabled, queues the execution in background.
        Otherwise, executes synchronously.
        """
        self.ensure_one()
        
        if not self.llm_enabled:
            raise UserError(_("LLM features are not enabled for this task"))
            
        if self.llm_execution_state == 'in_progress':
            raise UserError(_("Task is already executing"))
            
        # Create agent for task
        agent = self._create_crewai_agent()
        
        # Update execution state
        self.llm_execution_state = 'in_progress'
        
        if self.llm_async_execution:
            # Queue execution
            self.with_delay()._execute_task_background(agent)
            return True
        else:
            # Execute synchronously
            try:
                result = agent.execute_task(self.name, self.description)
                self.write({
                    'llm_execution_state': 'completed',
                    'llm_result': str(result) if result else False,
                })
            except Exception as e:
                _logger.exception("Task execution failed")
                self.write({
                    'llm_execution_state': 'failed',
                    'llm_result': str(e),
                })
                raise
            return True

    def _execute_task_job(self):
        """Background job for task execution."""
        try:
            task = self._to_crewai_task()
            result = task.execute()
            self._process_task_result(result)
            self.llm_execution_state = 'completed'
        except Exception as e:
            self._handle_execution_error(e)

    def _process_task_result(self, result):
        """Process task execution result.
        
        Args:
            result: Result from task.execute()
        """
        self.llm_result = result
        self.message_post(
            body=_("Task execution completed with result:\n%s") % result
        )
