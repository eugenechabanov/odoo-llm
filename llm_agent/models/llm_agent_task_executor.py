from odoo import api, fields, models, _
from odoo.exceptions import UserError


class LLMAgentTaskExecutor(models.AbstractModel):
    """Base model for LLM task execution.
    
    This model provides the fundamental structure for executing AI tasks,
    regardless of the specific implementation (CrewAI, etc).
    
    It follows the service dispatch pattern from llm.service.mixin to allow
    different implementations to handle task execution.
    """
    _name = 'llm.agent.task.executor'
    _description = 'LLM Agent Task Executor'
    _inherit = ['llm.agent.service.dispatch.mixin']

    service = fields.Selection(
        selection=lambda self: self._selection_service(),
        required=True,
        default='crewai',  # Default to CrewAI service if available
        help="Service to use for task execution"
    )

    @api.model
    def _get_available_services(self):
        """Get list of available task execution services.
        
        Returns:
            list: List of (code, label) tuples for available services
        """
        return []

    def execute_task(self, task_record, **kwargs):
        """Execute a task using service dispatch pattern.
        
        This method uses the service dispatch pattern to delegate task execution
        to the appropriate service implementation.
        
        Args:
            task_record: Record containing task information
            **kwargs: Additional arguments for specific implementations
            
        Returns:
            Result from the service implementation
            
        Example:
            # This will call crewai_execute_task if service='crewai'
            executor.execute_task(task, process='sequential')
        """
        return self._dispatch('execute_task', task_record, **kwargs)

    @api.model
    def validate_task_execution(self, task_record):
        """Validate if a task can be executed by AI.
        
        Args:
            task_record: Record containing task information
            
        Returns:
            llm.agent: The agent assigned to execute this task
            
        Raises:
            UserError: If validation fails
        """
        if not task_record.user_ids:
            raise UserError(_("Cannot execute AI task: No assignee specified"))
            
        agent = self._get_agent_for_task(task_record)
        if not agent:
            raise UserError(_("Cannot execute AI task: AI agent not found"))
            
        if not task_record.description:
            raise UserError(_("Cannot execute AI task: No description provided"))
            
        return agent
        
    @api.model
    def _get_agent_for_task(self, task_record):
        """Get the AI agent assigned to a task.
        
        Args:
            task_record: Record containing task information
            
        Returns:
            llm.agent: The assigned agent or None
        """
        return self.env['llm.agent'].search([
            ('user_id', 'in', task_record.user_ids.ids),
            ('active', '=', True)
        ], limit=1)

    @api.model
    def has_ai_agent_assigned(self, task_record):
        """Check if task has an AI agent assigned.
        
        Args:
            task_record: Record containing task information
            
        Returns:
            bool: True if an AI agent is assigned
        """
        return bool(self._get_agent_for_task(task_record))
