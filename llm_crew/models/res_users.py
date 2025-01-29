from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ResUsers(models.Model):
    _inherit = 'res.users'

    # Relations
    crew_agent_id = fields.One2many(
        'llm.crew.agent',
        'user_id',
        string="AI Agent Configuration"
    )
    
    # Computed Fields
    is_ai_agent = fields.Boolean(
        string="Is AI Agent",
        compute='_compute_is_ai_agent',
        search='_search_is_ai_agent',
        help="Whether this user is configured as an AI agent"
    )

    @api.depends('crew_agent_id', 'crew_agent_id.llm_enabled')
    def _compute_is_ai_agent(self):
        """Compute whether user is configured as AI agent"""
        for user in self:
            user.is_ai_agent = bool(user.crew_agent_id.filtered('llm_enabled'))

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

    def _to_crewai_agent(self):
        """Convert to CrewAI Agent if configured.
        
        Returns:
            crewai.Agent: CrewAI agent instance if configured, None otherwise
            
        Raises:
            UserError: If required fields are not set
        """
        self.ensure_one()
        
        if not self.is_ai_agent:
            return None
            
        return self.crew_agent_id._to_crewai_agent()
