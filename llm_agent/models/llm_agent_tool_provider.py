from odoo import fields, models


class LLMAgentToolProvider(models.Model):
    """Model for LLM agent tool providers.

    This model represents a provider of tools that can be used by LLM agents.
    Each provider can have multiple tools, and each agent must use tools from
    a single provider to ensure compatibility.
    """

    _name = "llm.agent.tool.provider"
    _description = "LLM Agent Tool Provider"
    _inherit = ["mail.thread", "llm.agent.service.dispatch.mixin"]

    name = fields.Char(required=True, tracking=True, help="Name of the tool provider")
    active = fields.Boolean(
        default=True,
        tracking=True,
        help="If unchecked, the provider will be hidden from selection",
    )
    description = fields.Text(
        required=True, tracking=True, help="Description of this tool provider"
    )
    tool_ids = fields.One2many(
        "llm.agent.tool",
        "provider_id",
        string="Tools",
        help="Tools provided by this provider",
    )
