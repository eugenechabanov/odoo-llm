from odoo import models, fields, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    llm_crew_agent_id = fields.Many2one('llm.crew.agent', string="AI Agent")
    is_ai_agent = fields.Boolean(compute='_compute_is_ai_agent', search='_search_is_ai_agent',
                               help="Whether this user is configured as an AI agent")

    @api.depends('llm_crew_agent_id')
    def _compute_is_ai_agent(self):
        """Compute whether user is configured as AI agent"""
        for user in self:
            user.is_ai_agent = bool(user.llm_crew_agent_id)

    def _search_is_ai_agent(self, operator, value):
        """Search users that are configured as AI agents"""
        if operator not in ('=', '!='):
            raise ValueError(_("Invalid operator for is_ai_agent search"))
            
        agents = self.env['llm.crew.agent'].search([('id', '!=', False)])
        user_ids = agents.mapped('user_id').ids
        
        if operator == '=':
            return [('id', 'in' if value else 'not in', user_ids)]
        else:
            return [('id', 'not in' if value else 'in', user_ids)]
