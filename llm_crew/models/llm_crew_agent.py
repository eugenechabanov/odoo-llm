from odoo import fields, models

from crewai import LLM, Agent


class LLMCrewAgent(models.Model):
    _name = "llm.crew.agent"
    _description = "LLM Crew Agent"
    _inherit = ["mail.thread"]

    name = fields.Char(required=True, tracking=True)
    user_id = fields.Many2one("res.users", required=True, tracking=True)
    llm_provider_id = fields.Many2one("llm.provider", required=True, tracking=True)
    llm_model_id = fields.Many2one("llm.model", required=True, tracking=True)
    role = fields.Text(required=True, tracking=True)
    goal = fields.Text(required=True, tracking=True)
    backstory = fields.Text(tracking=True)
    active = fields.Boolean(default=True)
    allow_delegation = fields.Boolean(default=False)

    _sql_constraints = [
        ("unique_user", "unique(user_id)", "An agent already exists for this user!")
    ]

    def _to_crewai_agent(self):
        return Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            allow_delegation=self.allow_delegation,
            llm=LLM(
                temperature=0.5,
                model=self.llm_model_id.name,
                api_key=self.llm_provider_id.api_key,
                base_url=self.llm_provider_id.api_base,
            ),
            step_callback=lambda step: (
                self.env["crm.team"]
                .search([("member_ids", "in", [self.user_id.id])], limit=1)
                .message_post(
                    body=self._generate_step_message(step),
                    message_type="comment",
                    author_id=self.user_id.partner_id.id,
                )
            ),
        )

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
