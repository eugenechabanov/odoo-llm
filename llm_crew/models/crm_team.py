from odoo import models, fields, api

class CRMTeam(models.Model):
    _inherit = 'crm.team'

    llm_crew_team_id = fields.Many2one('llm.crew.team', string="AI Crew", ondelete='cascade')
    is_ai_crew = fields.Boolean(compute='_compute_is_ai_crew', search='_search_is_ai_crew',
                              help="Whether this team is configured as an AI crew")

    @api.depends('llm_crew_team_id')
    def _compute_is_ai_crew(self):
        """Compute whether team is configured as AI crew"""
        for team in self:
            team.is_ai_crew = bool(team.llm_crew_team_id)

    def _search_is_ai_crew(self, operator, value):
        """Search teams that are configured as AI crews"""
        if operator not in ('=', '!='):
            raise ValueError(_("Invalid operator for is_ai_crew search"))
            
        crews = self.env['llm.crew.team'].search([('id', '!=', False)])
        team_ids = crews.mapped('team_id').ids
        
        if operator == '=':
            return [('id', 'in' if value else 'not in', team_ids)]
        else:
            return [('id', 'not in' if value else 'in', team_ids)]
