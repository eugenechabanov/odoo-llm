from odoo import models, fields, api

class Project(models.Model):
    _inherit = 'project.project'

    crew_team_ids = fields.One2many('llm.crew.team', 'project_id', string="AI Crews")
    crew_count = fields.Integer(compute='_compute_crew_count', string="Number of AI Crews")
    
    def _compute_crew_count(self):
        """Compute number of AI crews for this project"""
        for project in self:
            project.crew_count = len(project.crew_team_ids)
            
    def action_view_crews(self):
        """Open the crews view for this project"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'AI Crews',
            'res_model': 'llm.crew.team',
            'view_mode': 'tree,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
