from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ResUsers(models.Model):
    _inherit = ['res.users', 'llm.capability.mixin']

    llm_agent_role = fields.Text(
        string="Agent Role",
        help="Role description for the AI agent"
    )
    llm_agent_goal = fields.Text(
        string="Agent Goal",
        help="Primary goal or objective for the AI agent"
    )
    llm_agent_backstory = fields.Text(
        string="Agent Backstory",
        help="Background story to provide context for the AI agent"
    )
    llm_agent_allow_delegation = fields.Boolean(
        string="Allow Delegation",
        default=False,
        help="Allow this agent to delegate tasks to other agents"
    )
    llm_agent_tools = fields.Text(
        string="Agent Tools",
        help="JSON configuration for agent tools"
    )

    @api.depends('llm_enabled')
    def _compute_agent_fields_visibility(self):
        """Show/hide agent fields based on llm_enabled"""
        for user in self:
            user.show_agent_fields = user.llm_enabled

    def _to_crewai_agent(self):
        """Convert to CrewAI Agent if LLM enabled.
        
        Returns:
            crewai.Agent: CrewAI agent instance if LLM enabled, None otherwise
            
        Raises:
            UserError: If required fields are not set
        """
        self.ensure_one()
        if not self.llm_enabled:
            return None
            
        if not all([self.llm_agent_role, self.llm_agent_goal]):
            raise UserError(_(
                "Agent role and goal are required for user %s"
            ) % self.display_name)
            
        return self._create_crewai_agent()

    def _create_crewai_agent(self):
        """Create CrewAI agent instance.
        
        Returns:
            crewai.Agent: Configured CrewAI agent instance
        """
        from crewai import Agent
        
        # Get base configuration
        config = {
            'role': self.llm_agent_role,
            'goal': self.llm_agent_goal,
            'backstory': self.llm_agent_backstory,
            'llm': self._get_crewai_llm(),
            'allow_delegation': self.llm_agent_allow_delegation,
        }
        
        # Add tools if configured
        if self.llm_agent_tools:
            import json
            try:
                tools = json.loads(self.llm_agent_tools)
                if tools:
                    config['tools'] = tools
            except json.JSONDecodeError:
                pass  # Invalid JSON, ignore tools
                
        return Agent(**config)
