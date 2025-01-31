from odoo import models, fields

class ProjectTask(models.Model):
    _inherit = 'project.task'

    is_crew_task = fields.Boolean(string="Is Crew Task", default=False, tracking=True)
    expected_output = fields.Text(string="Expected Output", tracking=True)
    
