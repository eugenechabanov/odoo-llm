from odoo import fields, models, api

from crewai import LLM, Agent
from .odoo_mis_tools import OdooMisToolSet
from .mis_template_gen_tool import MISTemplateGenTool
from .mis_report_gen_tool import MISReportInstanceGenTool

class LLMAgent(models.Model):
    _name = "llm.agent"
    _description = "LLM Agent"
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
    allow_odoo_tools = fields.Boolean(default=False, tracking=True,
                                    help="Allow this agent to use Odoo-specific tools")
    
    # Hierarchical team structure
    parent_id = fields.Many2one('llm.agent', string='Manager', tracking=True,
                               help="The manager agent that this agent reports to")
    member_ids = fields.One2many('llm.agent', 'parent_id', string='Team Members',
                                help="Agents that report to this agent")
    is_manager = fields.Boolean(compute='_compute_is_manager', store=True,
                              help="Whether this agent manages other agents")
    

    _sql_constraints = [
        ("unique_user", "unique(user_id)", "An agent already exists for this user!"),
        ("no_recursive_hierarchy", "CHECK(parent_id != id)", "An agent cannot be its own manager!")
    ]

    @api.depends('member_ids')
    def _compute_is_manager(self):
        for agent in self:
            agent.is_manager = bool(agent.member_ids)

    def _to_crewai_agent(self):
        # Initialize tools list
        tools = []
        
        # Add Odoo tools if enabled
        if self.allow_odoo_tools:
            mis_tools = OdooMisToolSet(env=self.env)
            tools.extend(mis_tools.get_tools())

        return Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            allow_delegation=self.allow_delegation,
            tools=tools,
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
