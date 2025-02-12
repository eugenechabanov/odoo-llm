from odoo import api, fields, models


class LLMAgent(models.AbstractModel):
    """Base model for LLM agents.
    
    This abstract model defines the basic structure and interface that all LLM agent
    implementations must follow. It provides common fields and methods that are
    essential for any LLM agent integration.
    """
    _name = 'llm.agent.abstract'
    _description = 'Abstract LLM Agent'
    _inherit = ['mail.thread']

    name = fields.Char(
        required=True,
        tracking=True,
        help="Name of the agent"
    )
    active = fields.Boolean(
        default=True,
        tracking=True,
        help="If unchecked, the agent will be hidden from selection"
    )
    user_id = fields.Many2one(
        'res.users',
        string="Related User",
        required=True,
        tracking=True,
        help="User account associated with this agent",
        index=True
    )
    role = fields.Text(
        required=True,
        tracking=True,
        help="The role or responsibility of this agent"
    )
    goal = fields.Text(
        required=True,
        tracking=True,
        help="The primary objective or goal of this agent"
    )
    tool_ids = fields.Many2many(
        'llm.tool.abstract',
        string="Available Tools",
        help="Tools that this agent can use"
    )

    # Hierarchical team structure
    parent_id = fields.Many2one(
        'llm.agent.abstract',
        string="Manager",
        tracking=True,
        help="The manager agent that this agent reports to",
        index=True
    )
    member_ids = fields.One2many(
        'llm.agent.abstract',
        'parent_id',
        string="Team Members",
        help="Agents that report to this agent",
        index=True
    )
    is_manager = fields.Boolean(
        compute="_compute_is_manager",
        store=True,
        help="Whether this agent manages other agents"
    )

    _sql_constraints = [
        ('unique_user',
         'unique(user_id)',
         'An agent already exists for this user!'),
        ('no_recursive_hierarchy',
         'CHECK(parent_id != id)',
         'An agent cannot be its own manager!')
    ]

    @api.depends('member_ids')
    def _compute_is_manager(self):
        for agent in self:
            agent.is_manager = bool(agent.member_ids)

    @api.model
    def create_agent_instance(self, **kwargs):
        """Create an agent instance with the given configuration.
        
        This method should be implemented by concrete agent implementations to
        create their specific type of agent instance (e.g., CrewAI Agent).
        
        Args:
            **kwargs: Implementation-specific configuration options
            
        Returns:
            object: An instance of the specific agent implementation
            
        Raises:
            NotImplementedError: If the concrete class doesn't implement this method
        """
        raise NotImplementedError()

    def execute_task(self, **kwarg):
        """Execute a task using this agent.
        
        Args:
            **kwarg: Arguments required for task execution including:
                - description (str): Task description
                - expected_output (str, optional): Expected output format
                - additional fields as required by specific implementations
                
        Returns:
            dict: Result of task execution with at least:
                - success (bool): Whether task execution was successful
                - result (str): Output from the task execution
                - execution_time (float): Time taken to execute the task
                
        Raises:
            NotImplementedError: If the concrete class doesn't implement this method
        """
        raise NotImplementedError()

    def get_available_tools(self):
        """Get list of tools available to this agent.
        
        Returns:
            list: List of tool instances that this agent can use
        """
        return [tool.get_tool_instance() for tool in self.tool_ids if tool.active]
