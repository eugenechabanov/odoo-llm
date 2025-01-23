from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResUsers(models.Model):
    _inherit = 'res.users'

    model_id = fields.Many2one('llm.model', string='LLM Model',
        groups='base.group_system')
    system_prompt = fields.Text('System Prompt',
        groups='base.group_system')
    is_active = fields.Boolean('Active', default=True,
        groups='base.group_system')
    is_agent = fields.Boolean('Is AI Agent', compute='_compute_is_agent', store=True)

    @api.depends('groups_id')
    def _compute_is_agent(self):
        # During installation, just set all to False
        if self.env.context.get('module') == 'llm_agent':
            for user in self:
                user.is_agent = False
            return

        # After installation, use the proper group check
        try:
            agent_group = self.env.ref('llm_agent.group_agent')
            for user in self:
                user.is_agent = agent_group.id in user.groups_id.ids
        except ValueError:
            # If group doesn't exist yet, set all to False
            for user in self:
                user.is_agent = False

    @api.constrains('is_agent', 'model_id')
    def _check_agent_configuration(self):
        for user in self:
            if user.is_agent and not user.model_id:
                raise ValidationError(_("AI Agents must have an LLM model configured."))

    @api.model
    def _get_available_user_types(self):
        """Hide agent type from regular user creation"""
        types = super()._get_available_user_types()
        return [t for t in types if t[0] != 'agent']

    @api.model
    def create_agent(self, vals):
        """Helper method to create an agent user"""
        partner = self.env['res.partner'].create({
            'name': vals.get('name'),
            'email': vals.get('email'),
            'type': 'other',
        })

        try:
            agent_group = self.env.ref('llm_agent.group_agent')
            groups = [(6, 0, [agent_group.id])]
        except ValueError:
            groups = []

        return self.create({
            'name': vals.get('name'),
            'login': vals.get('email'),
            'partner_id': partner.id,
            'model_id': vals.get('model_id'),
            'system_prompt': vals.get('system_prompt'),
            'groups_id': groups,
            'is_active': True,
        })
