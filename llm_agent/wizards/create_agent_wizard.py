from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CreateAgentWizard(models.TransientModel):
    _name = 'create.agent.wizard'
    _description = 'Create Agent Wizard'

    # User Information
    name = fields.Char("Agent Name", required=True)
    login = fields.Char("Login/Email", required=True)
    parent_agent_id = fields.Many2one('res.users', string='Parent Agent',
                                    domain=[('is_agent', '=', True)])

    # Configuration Type
    use_existing_config = fields.Boolean("Use Existing Configuration")
    existing_config_id = fields.Many2one('llm.agent.config', string='Existing Configuration',
                                       domain=[('is_active', '=', True)])

    # New Configuration
    model_id = fields.Many2one("llm.model", string="LLM Model")
    role = fields.Char()
    goal = fields.Text()
    backstory = fields.Text()
    system_prompt = fields.Text()

    @api.onchange('use_existing_config')
    def _onchange_use_existing_config(self):
        """Clear fields based on configuration choice"""
        if self.use_existing_config:
            self.model_id = False
            self.role = False
            self.goal = False
            self.backstory = False
            self.system_prompt = False
        else:
            self.existing_config_id = False

    @api.constrains('use_existing_config', 'existing_config_id', 'model_id', 'role', 'goal', 'system_prompt')
    def _check_configuration(self):
        """Ensure either existing config is selected or new config is properly filled"""
        for wizard in self:
            if wizard.use_existing_config and not wizard.existing_config_id:
                raise ValidationError(_("Please select an existing configuration."))
            elif not wizard.use_existing_config:
                if not wizard.model_id:
                    raise ValidationError(_("Please select an LLM model."))
                if not wizard.role:
                    raise ValidationError(_("Please specify the agent's role."))
                if not wizard.goal:
                    raise ValidationError(_("Please specify the agent's goal."))
                if not wizard.system_prompt:
                    raise ValidationError(_("Please specify the system prompt."))

    def action_create_agent(self):
        """Create the agent user and its configuration"""
        self.ensure_one()

        # Temporarily disable constraint
        self = self.with_context(creating_agent_from_wizard=True)
        
        # Create the user
        user_vals = {
            'name': self.name,
            'login': self.login,
            'is_agent': True,
            'parent_agent_id': self.parent_agent_id.id,
        }
        user = self.env['res.users'].create(user_vals)

        # Handle configuration
        if self.use_existing_config:
            # Copy existing configuration
            config = self.existing_config_id.copy({
                'name': f"{self.name}'s Configuration",
                'user_id': user.id
            })
        else:
            # Create new configuration
            config = self.env['llm.agent.config'].create({
                'name': f"{self.name}'s Configuration",
                'user_id': user.id,
                'model_id': self.model_id.id,
                'role': self.role,
                'goal': self.goal,
                'backstory': self.backstory,
                'system_prompt': self.system_prompt,
                'is_active': True,
            })

        # Trigger recompute of is_agent
        user.env.add_to_compute(user._fields['is_agent'], user)
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.users',
            'res_id': user.id,
            'view_mode': 'form',
            'target': 'current',
        }
