from odoo import models, fields, api, _
from datetime import timedelta

class LLMShortTermMemory(models.TransientModel):
    _name = 'llm.memory.short_term'
    _description = 'Short Term Memory'
    _inherit = ['llm.memory.base']
    _order = 'create_date desc'
    
    # TransientModel has built-in cleanup after certain hours
    expiry = fields.Datetime(compute='_compute_expiry', store=True)
    task_id = fields.Many2one('llm.agent.task', tracking=True)
    
    @api.depends('create_date')
    def _compute_expiry(self):
        """Compute expiry date as 1 hour from creation - matching Odoo's default transient record lifetime"""
        for record in self:
            if record.create_date:
                record.expiry = record.create_date + timedelta(hours=1)
            else:
                record.expiry = fields.Datetime.now() + timedelta(hours=1)
    
    def save(self, data, metadata=None, agent=None, task_id=None):
        """Save a new short-term memory item"""
        return self.create({
            'name': f"STM-{fields.Datetime.now()}",
            'data': data,
            'metadata': metadata or {},
            'agent_id': agent,
            'task_id': task_id,
        })
    
    def search_memory(self, query, limit=3):
        """Search for relevant memories that haven't expired"""
        domain = [
            ('data', 'ilike', query),
            ('expiry', '>=', fields.Datetime.now())
        ]
        return self.search(domain, limit=limit)
