from odoo import models, fields, api, _

class BaseLLMMemory(models.AbstractModel):
    _name = 'llm.memory.base'
    _description = 'Base Memory Model'
    _inherit = ['mail.thread']

    name = fields.Char(required=True, tracking=True)
    agent_id = fields.Many2one('res.users', domain=[('is_agent', '=', True)], tracking=True)
    metadata = fields.Json(default=dict, tracking=True)
    data = fields.Text(tracking=True)  # The actual memory content
    create_date = fields.Datetime(readonly=True)
    write_date = fields.Datetime(readonly=True)

    def save(self, data, metadata=None, agent=None):
        """Base method for saving memory. To be implemented by child classes."""
        raise NotImplementedError()

    def search_memory(self, query, limit=3):
        """Base method for searching memory. To be implemented by child classes."""
        raise NotImplementedError()
