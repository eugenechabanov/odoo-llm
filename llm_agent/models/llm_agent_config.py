from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class LLMAgentConfig(models.Model):
    _name = 'llm.agent.config'
    _description = 'LLM Agent Configuration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(required=True, tracking=True)
    user_id = fields.Many2one('res.users', required=True, 
                             domain=[('is_agent', '=', True)],
                             ondelete='cascade',
                             tracking=True)
    
    # LLM Configuration
    model_id = fields.Many2one("llm.model", string="LLM Model", tracking=True)
    system_prompt = fields.Text("System Prompt", tracking=True)
    is_active = fields.Boolean("Active", default=True, tracking=True)
    
    # Role and Behavior
    role = fields.Char(tracking=True)
    goal = fields.Text(tracking=True)
    backstory = fields.Text(tracking=True)
    
    _sql_constraints = [
        ('unique_user', 'unique(user_id)', 'An agent can only have one configuration!')
    ]

    @api.constrains('model_id', 'system_prompt', 'role', 'goal')
    def _check_required_fields(self):
        """Ensure all required fields are set when agent is active"""
        for config in self:
            if config.is_active:
                if not config.model_id:
                    raise ValidationError(_("Active agents must have an LLM model configured."))
                if not config.system_prompt:
                    raise ValidationError(_("Active agents must have a system prompt."))
                if not config.role:
                    raise ValidationError(_("Active agents must have a role defined."))
                if not config.goal:
                    raise ValidationError(_("Active agents must have a goal defined."))

    def get_llm_response(self, prompt, **kwargs):
        """Get LLM response with full context"""
        if not self.is_active:
            raise ValidationError(_("Cannot get response from inactive agent."))
            
        # Get parent and child roles for context
        parent_role = self.user_id.parent_agent_id.agent_config_id.role if self.user_id.parent_agent_id else "none"
        child_roles = self.user_id.child_agent_ids.mapped('agent_config_id.role')
        
        context_prompt = f"""As a {self.role} with the goal of {self.goal}.

Background: {self.backstory or 'No specific background provided.'}

Organizational Context:
- You report to: {parent_role}
- You manage: {', '.join(child_roles) if child_roles else 'No direct reports'}

Task: {prompt}"""

        return self.user_id._get_llm_response(context_prompt, **kwargs)
