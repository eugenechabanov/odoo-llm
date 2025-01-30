from odoo import models, fields, api

class Project(models.Model):
    _inherit = 'project.project'

    llm_crew_project_id = fields.Many2one('llm.crew.project', string="AI Crew Project")
    
    def _to_crew_project(self):
        """Convert to CrewAI Project if AI project is configured"""
        self.ensure_one()
        if not self.llm_crew_project_id:
            return None
        return self.llm_crew_project_id._to_crew_project()
