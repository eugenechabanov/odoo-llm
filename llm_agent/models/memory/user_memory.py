from odoo import models, fields, api, _

class LLMUserMemory(models.Model):
    _name = 'llm.memory.user'
    _description = 'User Memory'
    _inherit = ['llm.memory.base']
    _order = 'create_date desc'
    
    user_id = fields.Many2one('res.users', required=True, tracking=True)
    category = fields.Selection([
        ('communication_style', 'Communication Style'),
        ('expertise', 'Technical Expertise'),
        ('domain_expertise', 'Domain Expertise'),
        ('output_preference', 'Output Preference'),
        ('language', 'Language Preference'),
        ('timezone', 'Timezone'),
    ], string='Category', index=True)
    
    def _get_normalized_data(self, value):
        """Normalize data for comparison by removing common prefixes and whitespace"""
        prefix = "Remember the details about the user: "
        if value.startswith(prefix):
            value = value[len(prefix):]
        return value.strip().lower()
    
    def save(self, value, user_id, metadata=None):
        """Save a user-related memory while avoiding duplicates
        
        Args:
            value: The memory value to save
            user_id: The user ID to associate with
            metadata: Optional metadata dictionary with 'category' key
        
        Returns:
            The created or existing memory record
        """
        data = f"Remember the details about the user: {value}"
        metadata = metadata or {}
        category = metadata.get('category')
        
        # Get normalized version of the data for comparison
        normalized_value = self._get_normalized_data(data)
        
        # Check for existing similar memory
        domain = [
            ('user_id', '=', user_id),
        ]
        
        # If category is specified, include it in duplicate check
        if category:
            domain.append(('category', '=', category))
        
        # Search for potential duplicates
        existing_records = self.search(domain)
        for record in existing_records:
            if self._get_normalized_data(record.data) == normalized_value:
                # Update metadata if needed
                if metadata != record.metadata:
                    record.write({'metadata': metadata})
                return record
        
        # Create new memory if no duplicate found
        vals = {
            'name': f"UM-{fields.Datetime.now()}",
            'data': data,
            'user_id': user_id,
            'metadata': metadata,
        }
        if category:
            vals['category'] = category
            
        return self.create(vals)
    
    def search_memory(self, query, category=None, limit=3):
        """Search for user-related memories
        
        Args:
            query: Search query
            category: Optional category to filter by
            limit: Maximum number of records to return
        """
        domain = [('data', 'ilike', query)]
        if category:
            domain.append(('category', '=', category))
        return self.search(domain, limit=limit, order='create_date desc')
