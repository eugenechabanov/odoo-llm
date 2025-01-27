import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

agent_group_name = "llm_agent.group_llm_agent"
class ResUsers(models.Model):
    _inherit = "res.users"

    # Hierarchy fields
    parent_agent_id = fields.Many2one('res.users', 
                                     string='Parent Agent',
                                     domain=[('is_agent', '=', True)])
    child_agent_ids = fields.One2many('res.users', 
                                     'parent_agent_id',
                                     string='Child Agents',
                                     domain=[('is_agent', '=', True)])
    
    # Agent configuration
    agent_config_id = fields.One2many('llm.agent.config', 'user_id', 
                                     string='Agent Configuration')
    is_agent = fields.Boolean("Is AI Agent", compute="_compute_is_agent", store=True)
    is_active = fields.Boolean("Active", default=True, groups="base.group_user")

    @api.model
    def get_agent_group(self):
        """Helper method to safely get the agent group."""
        try:
            group = self.env.ref(agent_group_name)
            _logger.info("Agent group found: %s (id: %s)", group.name, group.id)
            return group
        except ValueError:
            _logger.warning("Agent group '%s' not found", agent_group_name)
            return False

    def is_user_agent(self):
        """Check if the user is an AI agent."""
        # Skip during module installation or loading
        if self.env.context.get("module") == "llm_agent" or \
           self.env.context.get("install_mode"):
            return False

        agent_group = self.get_agent_group()
        is_agent = agent_group and agent_group.id in self.groups_id.ids

        return is_agent

    @api.depends("groups_id")
    def _compute_is_agent(self):
        """Compute if user is an agent based on group membership"""
        # Skip during module installation or loading
        if self.env.context.get("module") == "llm_agent" or \
           self.env.context.get("install_mode"):
            for user in self:
                user.is_agent = False
            return

        for user in self:
            user.is_agent = user.is_user_agent()

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set up agents with proper groups and partner."""
        # Skip agent setup during module installation
        if self.env.context.get("module") == "llm_agent" or \
           self.env.context.get("install_mode"):
            return super().create(vals_list)

        for vals in vals_list:
            if vals.get("is_agent") or self.env.context.get("default_is_agent"):
                # Create partner if needed
                if not vals.get("partner_id"):
                    vals["partner_id"] = (
                        self.env["res.partner"]
                        .create({
                            "name": vals.get("name"),
                            "email": vals.get("login"),
                            "type": "other",
                        })
                        .id
                    )

                # Add to required groups
                groups = []
                for xml_id in [agent_group_name, "base.group_user"]:
                    try:
                        groups.append(self.env.ref(xml_id).id)
                    except ValueError:
                        _logger.warning("Could not find group: %s", xml_id)

                if groups:
                    vals["groups_id"] = [(6, 0, groups)]

        return super().create(vals_list)

    @api.constrains('agent_config_id', 'is_agent')
    def _check_agent_configuration(self):
        """Ensure agents have configuration"""
        # Skip all validation during module installation or loading
        if self.env.context.get("module") == "llm_agent" or \
           self.env.context.get("install_mode"):
            return

        for user in self:
            # Skip validation during wizard creation
            if self.env.context.get('creating_agent_from_wizard'):
                continue
                
            if user.is_agent and not user.agent_config_id:
                raise ValidationError(_("AI Agents must have a configuration."))

    @api.constrains('parent_agent_id', 'child_agent_ids', 'is_agent')
    def _check_agent_hierarchy(self):
        for user in self:
            if user.parent_agent_id and not user.parent_agent_id.is_agent:
                raise ValidationError(_("Parent must be an AI agent."))
            if user.parent_agent_id == user:
                raise ValidationError(_("An agent cannot be its own parent."))
            if any(child.is_agent == False for child in user.child_agent_ids):
                raise ValidationError(_("Only AI agents can be added as child agents."))

    def get_all_subordinates(self):
        """Get all agents reporting to this agent (direct and indirect)"""
        subordinates = self.child_agent_ids
        for child in self.child_agent_ids:
            subordinates |= child.get_all_subordinates()
        return subordinates

    def get_full_hierarchy_up(self):
        """Get all parent agents up to the top"""
        hierarchy = self.env['res.users']
        current = self
        while current.parent_agent_id:
            hierarchy |= current.parent_agent_id
            current = current.parent_agent_id
        return hierarchy
