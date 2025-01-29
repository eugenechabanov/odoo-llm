from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class LLMCapabilityMixin(models.AbstractModel):
    """Mixin to add LLM capabilities to any model."""
    _name = 'llm.capability.mixin'
    _description = 'LLM Capability Mixin'

    llm_enabled = fields.Boolean(
        string="LLM Enabled",
        default=False,
        help="Enable LLM capabilities for this record"
    )
    llm_provider_id = fields.Many2one(
        'llm.provider',
        string="LLM Provider",
        help="LLM provider to use for this record",
        ondelete='restrict'
    )
    llm_model_id = fields.Many2one(
        'llm.model',
        string="LLM Model",
        domain="[('provider_id', '=', llm_provider_id), ('model_use', '=', 'chat')]",
        help="Specific model to use for this record",
        ondelete='restrict'
    )
    llm_memory_enabled = fields.Boolean(
        string="Enable Memory",
        default=True,
        help="Enable memory capabilities"
    )
    llm_memory_config = fields.Text(
        string="Memory Configuration",
        help="JSON configuration for memory settings"
    )
    llm_max_iterations = fields.Integer(
        string="Max Iterations",
        default=15,
        help="Maximum number of iterations for LLM operations"
    )
    llm_execution_state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ], string="Execution State",
        default='draft',
        tracking=True,
        help="Current state of LLM execution"
    )
    llm_result = fields.Text(
        string="Result",
        help="Result of the last LLM execution"
    )
    llm_async_execution = fields.Boolean(
        string="Async Execution",
        help="Execute LLM tasks asynchronously",
        default=False
    )

    @api.onchange('llm_provider_id')
    def _onchange_llm_provider_id(self):
        """Clear model when provider changes"""
        self.llm_model_id = False

    def _get_crewai_llm(self):
        """Get LLM instance configured for CrewAI.
        
        Returns:
            LangChain LLM instance compatible with CrewAI
            
        Raises:
            UserError: If provider not configured or not supported
        """
        self.ensure_one()
        if not self.llm_provider_id:
            raise UserError(_("No LLM provider configured for %s") % self.display_name)

        # Get model (or default) from provider
        model = self.llm_model_id or self.llm_provider_id.model_ids.filtered(
            lambda m: m.model_use == 'chat' and m.default
        )
        
        if not model:
            raise UserError(_("No chat model configured for provider %s") % 
                          self.llm_provider_id.name)

        # Import appropriate LangChain class based on provider service
        service = self.llm_provider_id.service
        if service == 'openai':
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model.name,
                openai_api_key=self.llm_provider_id.api_key,
                openai_api_base=self.llm_provider_id.api_base or None,
                temperature=0.7
            )
        elif service == 'anthropic':
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=model.name,
                anthropic_api_key=self.llm_provider_id.api_key,
                temperature=0.7
            )
        else:
            raise UserError(_("Provider service %s is not supported for CrewAI integration") % 
                          service)

    def _handle_execution_error(self, error):
        """Handle execution errors.
        
        Args:
            error: The exception that occurred
        """
        self.ensure_one()
        self.message_post(body=_(
            "LLM execution failed with error: %s") % str(error)
        )
        self.llm_execution_state = 'failed'

    def _get_llm(self):
        """Get LLM instance for this record.
        
        Returns:
            object: LLM instance compatible with CrewAI
        """
        self.ensure_one()
        
        if not self.llm_enabled:
            return None
            
        if not self.llm_provider_id or not self.llm_model_id:
            return None
            
        return self.llm_provider_id._get_crewai_llm(
            model=self.llm_model_id.name
        )

    def _execute_llm(self, execute_fn):
        """Execute LLM operation with state management.
        
        Args:
            execute_fn: Function that performs the actual execution
            
        Returns:
            bool: True if execution started successfully
            
        Raises:
            UserError: If execution cannot start
            Exception: If synchronous execution fails
        """
        self.ensure_one()
        
        if not self.llm_enabled:
            raise UserError("LLM features are not enabled")
            
        if self.llm_execution_state == 'in_progress':
            raise UserError("Already executing")
            
        # Update execution state
        self.llm_execution_state = 'in_progress'
        
        if self.llm_async_execution:
            # Queue execution
            execute_fn()
            return True
        else:
            # Execute synchronously
            try:
                result = execute_fn()
                self._handle_llm_result(result)
            except Exception as e:
                self._handle_llm_error(e)
                raise
            return True
            
    def _handle_llm_result(self, result):
        """Handle successful LLM execution result.
        
        Args:
            result: Result from LLM execution
        """
        self.write({
            'llm_execution_state': 'completed',
            'llm_result': str(result) if result else False,
        })
        if hasattr(self, 'message_post'):
            self.message_post(
                body=f"Execution completed with result:\n{result}"
            )
            
    def _handle_llm_error(self, error):
        """Handle LLM execution error.
        
        Args:
            error: Exception that occurred
        """
        _logger.exception("LLM execution failed")
        self.write({
            'llm_execution_state': 'failed',
            'llm_result': str(error),
        })
        if hasattr(self, 'message_post'):
            self.message_post(
                body=f"Execution failed with error:\n{error}",
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
