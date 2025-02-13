from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ProjectTask(models.Model):
    """Extends project task for AI execution."""
    _inherit = 'project.task'

    expected_output = fields.Text(
        string="Expected Output",
        tracking=True,
        help="Expected output format or success criteria for AI task execution"
    )
    ai_result = fields.Text(
        string="AI Result", 
        tracking=True
    )
    execution_time = fields.Float(
        string="Execution Time (s)", 
        tracking=True
    )
    process = fields.Selection(
        [("sequential", "Sequential"), ("hierarchical", "Hierarchical")],
        default="sequential",
        required=True,
        help="Sequential: Each task has its own agent\n"
             "Hierarchical: Manager agent delegates to team members"
    )
    is_ai_executable = fields.Boolean(
        compute="_compute_is_ai_executable",
        help="Whether this task can be executed by AI"
    )

    @api.depends('user_ids')
    def _compute_is_ai_executable(self):
        """Determine if task can be executed by AI."""
        executor = self._get_task_executor()
        for task in self:
            task.is_ai_executable = executor.has_ai_agent_assigned(task)

    def _get_task_executor(self):
        """Get task executor with CrewAI service.
        
        Returns:
            llm.agent.task.executor: Task executor record configured with CrewAI service
            
        Raises:
            UserError: If no task executor is configured with CrewAI service
        """
        ExecutorModel = self.env['llm.agent.task.executor']
        executor = ExecutorModel.search([('service', '=', 'crewai')], limit=1)
        if not executor:
            raise UserError(_("No task executor found with CrewAI service. Please configure one in Agents Configuration > Task Executors."))
        return executor

    def action_execute_ai_task(self):
        """Execute task using configured executor."""
        self.ensure_one()

        if not self.is_ai_executable:
            raise UserError(_("This task cannot be executed by AI. Please ensure it is assigned to an AI agent."))

        # Get the executor with CrewAI service
        executor = self._get_task_executor()
        
        try:
            # Execute and track time
            import time
            start_time = time.time()
            
            result = executor.execute_task(
                self,
                process=self.process
            )
            
            execution_time = time.time() - start_time

            # Update task results
            self.write({
                'ai_result': result,
                'execution_time': execution_time,
                'kanban_state': 'done'
            })

            # Post success message
            self._post_execution_message(execution_time, result)

        except Exception as e:
            self.kanban_state = 'blocked'
            self._post_error_message(str(e))
            raise

    def _post_execution_message(self, execution_time, result):
        """Post success message in chatter."""
        agent = self.env['llm.agent.task.executor']._get_agent_for_task(self)
        message = f"""<b>AI Task Completed</b><br/>
Execution Time: {execution_time:.2f}s<br/>
Process: {self.process}<br/>"""
        
        if self.process == 'hierarchical':
            message += f"Manager: {agent.role}<br/>"
            
        message += f"<br/>{result}"
        
        self.message_post(
            body=message,
            message_type="comment",
            author_id=agent.user_id.partner_id.id
        )

    def _post_error_message(self, error):
        """Post error message in chatter."""
        agent = self.env['llm.agent.task.executor']._get_agent_for_task(self)
        self.message_post(
            body=f"<b>AI Task Failed</b><br/>{error}",
            message_type="comment",
            author_id=agent.user_id.partner_id.id
        )
