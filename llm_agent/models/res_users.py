from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    model_id = fields.Many2one('llm.model', string='LLM Model',
        groups='base.group_user')  # Allow all users to read
    system_prompt = fields.Text('System Prompt',
        groups='base.group_user')
    is_active = fields.Boolean('Active', default=True,
        groups='base.group_user')
    is_agent = fields.Boolean('Is AI Agent', compute='_compute_is_agent', store=True)

    @api.model
    def get_agent_group(self):
        """Helper method to safely get the agent group.
        Returns False if the group doesn't exist yet (e.g. during installation)."""
        try:
            group = self.env.ref('llm_agent.group_agent')
            _logger.info("Agent group found: %s (id: %s)", group.name, group.id)
            return group
        except ValueError:
            _logger.warning("Agent group 'llm_agent.group_agent' not found")
            return False

    def is_user_agent(self):
        """Check if the user is an AI agent.
        Returns False during installation or if group doesn't exist yet."""
        if self.env.context.get('module') == 'llm_agent':
            _logger.info("Skipping agent check during module installation")
            return False
            
        agent_group = self.get_agent_group()
        is_agent = agent_group and agent_group.id in self.groups_id.ids
        _logger.info(
            "Checking if user %s (id: %s) is agent: %s. Groups: %s",
            self.name, self.id, is_agent,
            ', '.join(self.groups_id.mapped('name'))
        )
        return is_agent

    @api.depends('groups_id')
    def _compute_is_agent(self):
        for user in self:
            user.is_agent = user.is_user_agent()

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to properly set up agents when created through UI"""
        for vals in vals_list:
            if self.env.context.get('default_is_agent'):
                # Create partner with email
                if not vals.get('partner_id'):
                    vals['partner_id'] = self.env['res.partner'].create({
                        'name': vals.get('name'),
                        'email': vals.get('login'),
                        'type': 'other',
                    }).id
                
                # Add to required groups
                groups = []
                for xml_id in ['llm_agent.group_agent', 'base.group_user']:
                    try:
                        groups.append(self.env.ref(xml_id).id)
                    except ValueError:
                        _logger.warning("Could not find group: %s", xml_id)
                
                if groups:
                    vals['groups_id'] = [(6, 0, groups)]

        return super().create(vals_list)

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
