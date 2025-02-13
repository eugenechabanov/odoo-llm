from odoo import api, models, _
from odoo.exceptions import UserError

from crewai import Agent, LLM


class LLMAgent(models.Model):
    """Extends the base LLM agent model to support CrewAI integration."""
    _inherit = 'llm.agent'

    def _generate_step_message(self, step):
        """Generate a message for a step in the agent's execution.
        
        Args:
            step: The step information from CrewAI
            
        Returns:
            str: Formatted message describing the step
        """
        return f"""Step: {step.step}
Input: {step.input}
Output: {step.output}"""

    @api.model
    def _get_available_services(self):
        """Add CrewAI service to available services."""
        services = super()._get_available_services()
        services.append(('crewai', 'CrewAI'))
        return services

    def crewai_get_instance(self, **kwargs):
        """Get a CrewAI Agent instance based on this record.
        
        This method follows the service dispatch pattern from llm.service.mixin.
        The method name is prefixed with 'crewai_' to match the service code.
        
        Returns:
            crewai.Agent: The CrewAI Agent instance configured with this record's settings.
        
        Raises:
            UserError: If required configuration is missing.
        """
        self.ensure_one()

        if not self.llm_model_id:
            raise UserError(_("LLM Model is required for CrewAI agent"))

        if not self.role:
            raise UserError(_("Role is required for CrewAI agent"))

        if not self.goal:
            raise UserError(_("Goal is required for CrewAI agent"))

        # Create the CrewAI agent with our configuration
        agent = Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory or "",
            allow_delegation=self.is_manager,
            verbose=True,
            llm=LLM(
                temperature=0.5,
                model=self.llm_model_id.name,
                api_key=self.llm_provider_id.api_key,
                base_url=self.llm_provider_id.api_base,
            ),
            step_callback=lambda step: (
                self.message_post(
                    body=self._generate_step_message(step),
                    message_type="comment",
                    author_id=self.user_id.partner_id.id,
                )
            ),
        )
        
        return agent
