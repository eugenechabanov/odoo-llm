from odoo import models, fields, api, _

class LLMUserMemory(models.Model):
    _name = 'llm.memory.user'
    _description = 'User Memory'
    _inherit = ['llm.memory.base']
    _order = 'create_date desc'
    
    user_id = fields.Many2one('res.users', required=True, tracking=True)
    
    def save(self, value, user_id, metadata=None):
        """Save a user-related memory while avoiding duplicates
        
        Args:
            value: The memory value to save
            user_id: The user ID to associate with
            metadata: Optional metadata dictionary
        
        Returns:
            The created or existing memory record
        """
        data = f"Remember the details about the user: {value}"
        metadata = metadata or {}
        
        # Check for existing similar memory
        domain = [
            ('user_id', '=', user_id),
            ('data', '=', data)
        ]
        
        # If category is specified, include it in duplicate check
        if metadata.get('category'):
            domain.append(('metadata', 'ilike', f'"category":"{metadata["category"]}"'))
        
        existing = self.search(domain, limit=1)
        if existing:
            # Update metadata if needed
            if metadata and metadata != existing.metadata:
                existing.write({'metadata': metadata})
            return existing
        
        # Create new memory if no duplicate found
        return self.create({
            'name': f"UM-{fields.Datetime.now()}",
            'data': data,
            'user_id': user_id,
            'metadata': metadata,
        })
    
    def search_memory(self, query, limit=3):
        """Search for user-related memories"""
        return self.search([
            ('data', 'ilike', query)
        ], limit=limit, order='create_date desc')
