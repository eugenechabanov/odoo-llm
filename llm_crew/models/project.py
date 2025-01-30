from odoo import models, fields, api

class Project(models.Model):
    _inherit = 'project.project'

    llm_crew_project_id = fields.Many2one('llm.crew.project', string="AI Crew Project")
