from odoo import models, fields, api, _

class LLMLongTermMemory(models.Model):
    _name = 'llm.memory.long_term'
    _description = 'Long Term Memory'
    _inherit = ['llm.memory.base']
    _order = 'execution_date desc, quality_score desc'
    
    task_description = fields.Text(required=True, tracking=True)
    expected_output = fields.Text(tracking=True)
    quality_score = fields.Float(tracking=True, default=0.0,
                               help="Score indicating the quality/relevance of this memory")
    execution_date = fields.Datetime(default=fields.Datetime.now, tracking=True)
    
    def save(self, task, expected_output, agent=None, quality=None, metadata=None):
        """Save a new long-term memory item"""
        return self.create({
            'name': f"LTM-{fields.Datetime.now()}",
            'task_description': task,
            'expected_output': expected_output,
            'quality_score': quality or 0.0,
            'agent_id': agent,
            'metadata': metadata or {},
            'data': f"Task: {task}\nOutput: {expected_output}",  # Storing in base field for consistency
        })
    
    def search_memory(self, task, latest_n=3):
        """Search for relevant memories based on task description"""
        domain = [('task_description', 'ilike', task)]
        return self.search(
            domain,
            limit=latest_n,
            order='quality_score desc, execution_date desc'
        )
    
    def update_quality_score(self, score):
        """Update the quality score of this memory"""
        self.ensure_one()
        if 0.0 <= score <= 1.0:
            self.write({'quality_score': score})
        else:
            raise ValueError("Quality score must be between 0 and 1")
