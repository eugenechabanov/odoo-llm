from odoo import fields, models


class LLMAgentTool(models.Model):
    """Base model for LLM agent tools.

    This model defines the basic structure and interface that all LLM agent tool
    implementations must follow. It provides common fields and methods that are
    essential for any LLM agent tool integration.
    """

    _name = "llm.agent.tool"
    _description = "LLM Agent Tool"
    _inherit = ["mail.thread", "llm.agent.service.dispatch.mixin"]

    name = fields.Char(required=True, tracking=True, help="Name of the tool")
    active = fields.Boolean(
        default=True,
        tracking=True,
        help="If unchecked, the tool will be hidden from selection",
    )
    description = fields.Text(
        required=True, tracking=True, help="Description of what this tool does"
    )
    provider_id = fields.Many2one(
        "llm.agent.tool.provider",
        string="Tool Provider",
        required=True,
        tracking=True,
        help="Provider that offers this tool",
        index=True,
    )
