from odoo import api, fields, models, exceptions


class LLMAgent(models.Model):
    """Base model for LLM agents.

    This model defines the basic structure and interface that all LLM agent
    implementations must follow. It provides common fields and methods that are
    essential for any LLM agent integration.
    """

    _name = "llm.agent"
    _description = "LLM Agent"
    _inherit = ["mail.thread", "llm.agent.service.dispatch.mixin"]

    name = fields.Char(required=True, tracking=True, help="Name of the agent")
    active = fields.Boolean(
        default=True,
        tracking=True,
        help="If unchecked, the agent will be hidden from selection",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Related User",
        required=True,
        tracking=True,
        help="User account associated with this agent",
        index=True,
    )
    role = fields.Text(
        required=True, tracking=True, help="Role description for the agent"
    )
    goal = fields.Text(
        required=True, tracking=True, help="Goal that the agent should achieve"
    )
    backstory = fields.Text(tracking=True, help="Optional backstory for the agent")
    llm_provider_id = fields.Many2one(
        "llm.provider",
        string="LLM Provider",
        required=True,
        tracking=True,
        help="Provider used by this agent for language model capabilities",
        index=True,
    )
    llm_model_id = fields.Many2one(
        "llm.model",
        string="LLM Model",
        required=True,
        tracking=True,
        domain="[('provider_id', '=', llm_provider_id)]",
        help="The specific LLM model to use for this agent",
    )
    tool_ids = fields.Many2many(
        "llm.agent.tool",
        string="Tools that LLM Agent can use",
        tracking=True,
        help="Tools that this agent can use",
    )

    # Hierarchical team structure
    parent_id = fields.Many2one(
        "llm.agent",
        string="Manager",
        tracking=True,
        help="The manager agent that this agent reports to",
        index=True,
    )
    member_ids = fields.One2many(
        "llm.agent",
        "parent_id",
        string="Team Members",
        help="Agents that report to this agent",
        index=True,
    )
    is_manager = fields.Boolean(
        compute="_compute_is_manager",
        store=True,
        help="Whether this agent manages other agents",
    )

    _sql_constraints = [
        ("unique_user", "unique(user_id)", "An agent already exists for this user!"),
        (
            "no_recursive_hierarchy",
            "CHECK(parent_id != id)",
            "An agent cannot be its own manager!",
        ),
    ]

    @api.depends("member_ids")
    def _compute_is_manager(self):
        for agent in self:
            agent.is_manager = bool(agent.member_ids)

    @api.constrains('tool_ids')
    def _check_tools_same_provider(self):
        """Ensure all selected tools belong to the same provider."""
        for agent in self:
            providers = agent.tool_ids.mapped('provider_id')
            if len(providers) > 1:
                raise exceptions.ValidationError("All selected tools must belong to the same provider.")
