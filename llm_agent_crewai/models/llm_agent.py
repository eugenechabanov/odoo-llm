from odoo import api, models, _
from odoo.exceptions import UserError

from crewai import Agent, LLM


class LLMAgent(models.Model):
    """Extends the base LLM agent model to support CrewAI integration."""
    _inherit = 'llm.agent'

    def _generate_step_message(self, step):
        """Generate formatted message for step callback.

        Args:
            step: AgentAction or AgentFinish object from CrewAI

        Returns:
            string: html_message
        """
        # Extract values with defaults
        thought = getattr(step, "thought", "No thought provided")
        tool = getattr(step, "tool", None)
        tool_input = getattr(step, "tool_input", None)
        output = getattr(step, "output", None)
        result = getattr(step, "result", None)

        # Build HTML message
        html_parts = [
            f"<b>Agent {self.name}:</b><br/>",
            f"<b>Thought:</b> {thought}<br/>",
            f"<b>Tool:</b> {tool}<br/>" if tool else "",
            f"<b>Tool Input:</b> {tool_input}<br/>" if tool_input else "",
            f"<b>Output:</b> {output}"
            if output
            else (f"<b>Result:</b> {result}" if result else str(step)),
        ]
        html_message = "".join(html_parts)

        return html_message

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

        # Get tools from the agent's tool_ids
        tools = []
        for tool in self.tool_ids:
            tool_instance = tool.get_instance()
            if tool_instance:
                tools.append(tool_instance)

        # Create the CrewAI agent with our configuration
        agent = Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory or "",
            allow_delegation=self.is_manager,
            tools=tools,
            verbose=True,
            llm=LLM(
                temperature=0.5,
                model=self.llm_model_id.name,
                api_key=self.llm_model_id.provider_id.api_key,
                base_url=self.llm_model_id.provider_id.api_base,
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
