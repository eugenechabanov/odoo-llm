from odoo import models


class LLMAgentExternalInstanceMixin(models.AbstractModel):
    """Mixin for models that need to create external runtime instances.
    
    This mixin provides a common interface for models that need to create
    runtime instances of external objects (like CrewAI Agents or Tools).
    These instances are used during actual execution/runtime of LLM operations,
    as opposed to their Odoo model representations which are used for
    configuration and storage.
    """
    _name = 'llm.agent.external.mixin'
    _description = 'LLM External Instance Mixin'

    def get_instance(self, **kwargs):
        """Get a runtime instance of the external object.
        
        This method should be implemented by concrete implementations to
        return their specific type of runtime instance (e.g., CrewAI Agent/Tool).
        The returned instance will be used during actual LLM operations.
        
        Args:
            **kwargs: Implementation-specific configuration options
            
        Returns:
            object: A runtime instance of the specific implementation
            
        Raises:
            NotImplementedError: If not implemented by concrete class
        """
        raise NotImplementedError()
