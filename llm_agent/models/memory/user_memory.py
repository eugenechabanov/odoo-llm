from odoo import models, fields, api, _

class LLMUserMemory(models.Model):
    _name = 'llm.memory.user'
    _description = 'User Memory'
    _inherit = ['llm.memory.base']
    _order = 'create_date desc'
    
    user_id = fields.Many2one('res.users', required=True, tracking=True)
    
    def save(self, value, user_id, metadata=None):
        """Save a user-related memory"""
        data = f"Remember the details about the user: {value}"
        return self.create({
            'name': f"UM-{fields.Datetime.now()}",
            'data': data,
            'user_id': user_id,
            'metadata': metadata or {},
        })
    
    def search_memory(self, query, limit=3):
        """Search for user-related memories"""
        return self.search([
            ('data', 'ilike', query)
        ], limit=limit, order='create_date desc')
