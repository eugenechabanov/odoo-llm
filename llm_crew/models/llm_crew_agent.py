from odoo import api, fields, models, _
from odoo.exceptions import UserError


class LLMCrewAgent(models.Model):
    """AI Agent configuration and capabilities."""
    _name = 'llm.crew.agent'
    _description = 'LLM Crew Agent'
    _inherit = ['llm.capability.mixin', 'mail.thread']
    _order = 'name'

    name = fields.Char(related='user_id.name', store=True, readonly=True)
    active = fields.Boolean(default=True)
    
    # Relations
    user_id = fields.Many2one(
        'res.users',
        string="User",
        required=True,
        ondelete='cascade',
        index=True
    )
    
    # Agent Configuration
    role = fields.Text(
        string="Role",
        required=True,
        help="Role description for the AI agent"
    )
    goal = fields.Text(
        string="Goal",
        required=True,
        help="Primary goal or objective for the AI agent"
    )
    backstory = fields.Text(
        string="Backstory",
        help="Background story to provide context for the AI agent"
    )
    allow_delegation = fields.Boolean(
        string="Allow Delegation",
        default=False,
        help="Allow this agent to delegate tasks to other agents"
    )
    tools = fields.Text(
        string="Tools",
        help="JSON configuration for agent tools"
    )

    _sql_constraints = [
        ('unique_user',
         'unique(user_id)',
         'An AI agent already exists for this user!')
    ]

    def name_get(self):
        """Custom name display including role."""
        result = []
        for agent in self:
            name = f"{agent.name} ({agent.role})" if agent.role else agent.name
            result.append((agent.id, name))
        return result

    def _get_agent_tools(self):
        """Get agent tools from JSON configuration.
        
        Returns:
            dict: Agent tools configuration
        """
        if self.tools:
            import json
            try:
                tools = json.loads(self.tools)
                if tools:
                    return tools
            except json.JSONDecodeError:
                pass  # Invalid JSON, ignore tools
        return {}

    def _to_crewai_agent(self):
        """Convert to CrewAI Agent.
        
        Returns:
            crewai.Agent: CrewAI agent instance
            
        Raises:
            UserError: If required fields are not set
        """
        self.ensure_one()
        
        if not self.llm_enabled:
            raise UserError(_("LLM capabilities not enabled for agent %s") % self.name)
            
        if not all([self.role, self.goal]):
            raise UserError(_("Role and goal are required for agent %s") % self.name)

        from crewai import Agent
        return Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            llm=self._get_crewai_llm(),
            allow_delegation=self.allow_delegation,
            tools=self._get_agent_tools()
        )
