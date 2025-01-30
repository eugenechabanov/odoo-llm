from odoo import api, fields, models, _

class ResUsers(models.Model):
    _inherit = 'res.users'

    # Relations
    llm_crew_agent_id = fields.Many2one(
        'llm.crew.agent',
        string="AI Agent"
    )
    
    # Computed Fields
    is_ai_agent = fields.Boolean(
        string="Is AI Agent",
        compute='_compute_is_ai_agent',
        search='_search_is_ai_agent',
        help="Whether this user is configured as an AI agent"
    )

    @api.depends('llm_crew_agent_id')
    def _compute_is_ai_agent(self):
        """Compute whether user is configured as AI agent"""
        for user in self:
            user.is_ai_agent = bool(user.llm_crew_agent_id)

    def _search_is_ai_agent(self, operator, value):
        """Search users that are configured as AI agents"""
        if operator not in ('=', '!='):
            raise ValueError(_("Invalid operator for is_ai_agent search"))
            
        agents = self.env['llm.crew.agent'].search([('llm_enabled', '=', True)])
        user_ids = agents.mapped('user_id').ids
        
        if operator == '=':
            return [('id', 'in' if value else 'not in', user_ids)]
        else:
            return [('id', 'not in' if value else 'in', user_ids)]

    def _to_crew_agent(self):
        """Convert to CrewAI Agent if AI agent is configured"""
        self.ensure_one()
        if not self.llm_crew_agent_id:
            return None
        return self.llm_crew_agent_id._to_crew_agent()
