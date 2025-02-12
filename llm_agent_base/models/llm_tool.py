from odoo import api, fields, models


class LLMTool(models.AbstractModel):
    """Base model for LLM tools.
    
    This abstract model defines the basic structure and interface that all LLM tools
    must follow. Tools are capabilities that can be provided to agents to help them
    accomplish their tasks.
    """
    _name = 'llm.tool.abstract'
    _description = 'Abstract LLM Tool'

    name = fields.Char(
        required=True,
        help="Name of the tool"
    )
    active = fields.Boolean(
        default=True,
        help="If unchecked, the tool will be hidden from selection"
    )
    description = fields.Text(
        required=True,
        help="Detailed description of what the tool does and how to use it"
    )

    @api.model
    def get_tool_instance(self):
        """Get a tool instance that can be used by an agent.
        
        This method should be implemented by concrete tool implementations to
        return their specific type of tool instance (e.g., a function wrapper
        for CrewAI).
        
        Returns:
            object: An instance of the specific tool implementation
            
        Raises:
            NotImplementedError: If the concrete class doesn't implement this method
        """
        raise NotImplementedError()

    def execute(self, **kwargs):
        """Execute the tool with given parameters.
        
        Args:
            **kwargs: Tool-specific parameters
            
        Returns:
            dict: Result of tool execution with at least:
                - success (bool): Whether execution was successful
                - result (any): Output from the tool execution
                
        Raises:
            NotImplementedError: If the concrete class doesn't implement this method
        """
        raise NotImplementedError()
