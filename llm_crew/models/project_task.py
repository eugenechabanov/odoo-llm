from odoo import models, fields, api

class ProjectTask(models.Model):
    _inherit = 'project.task'

    llm_crew_task_id = fields.Many2one('llm.crew.task', string="AI Task")
    is_ai_task = fields.Boolean(compute='_compute_is_ai_task', search='_search_is_ai_task',
                              help="Whether this task is configured as an AI task")

    @api.depends('llm_crew_task_id')
    def _compute_is_ai_task(self):
        """Compute whether task is configured as AI task"""
        for task in self:
            task.is_ai_task = bool(task.llm_crew_task_id)

    def _search_is_ai_task(self, operator, value):
        """Search tasks that are configured as AI tasks"""
        if operator not in ('=', '!='):
            raise ValueError(_("Invalid operator for is_ai_task search"))
            
        tasks = self.env['llm.crew.task'].search([('id', '!=', False)])
        task_ids = tasks.mapped('task_id').ids
        
        if operator == '=':
            return [('id', 'in' if value else 'not in', task_ids)]
        else:
            return [('id', 'not in' if value else 'in', task_ids)]
