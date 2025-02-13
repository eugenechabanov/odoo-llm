from odoo import api, fields, models, _
from odoo.exceptions import UserError


class LLMAgentServiceDispatchMixin(models.AbstractModel):
    """Mixin for LLM agent service dispatch pattern.
    
    This mixin provides the common functionality for service-based dispatch pattern
    used by both LLM agents and tools. It allows different implementations to register
    their services and handle method dispatch based on the selected service.
    """
    _name = 'llm.agent.service.dispatch.mixin'
    _description = 'LLM Agent Service Dispatch Mixin'

    service = fields.Selection(
        selection=lambda self: self._selection_service(),
        tracking=True,
        help="The service implementation to use"
    )

    def get_instance(self, **kwargs):
        """Get a runtime instance using dispatch pattern.
        
        This method uses dispatch pattern to delegate instance creation to the
        appropriate service implementation.
        
        Args:
            **kwargs: Implementation-specific configuration options
            
        Returns:
            object: A runtime instance of the specific implementation
            
        Raises:
            UserError: If service is not configured
            NotImplementedError: If service implementation is missing
        """
        return self._dispatch('get_instance', **kwargs)

    def _dispatch(self, method, *args, **kwargs):
        """Dispatch method call to appropriate service implementation.
        
        Args:
            method: Name of the method to dispatch
            *args: Positional arguments to pass to implementation
            **kwargs: Keyword arguments to pass to implementation
            
        Returns:
            Result from service implementation
            
        Raises:
            UserError: If service is not configured
            NotImplementedError: If service implementation is missing
        """
        if not self.service:
            raise UserError(_("%s service not configured") % self._description)

        service_method = f"{self.service}_{method}"
        if not hasattr(self, service_method):
            raise NotImplementedError(
                _("Method %s not implemented for service %s") % (method, self.service)
            )

        return getattr(self, service_method)(*args, **kwargs)

    @api.model
    def _selection_service(self):
        """Get all available services from implementations.
        
        Returns:
            list: List of (code, label) tuples for available services
        """
        services = []
        for service in self._get_available_services():
            services.append(service)
        return services

    @api.model
    def _get_available_services(self):
        """Get available services from this implementation.
        
        This method should be extended by service implementations to add their
        service to the list.
        
        Returns:
            list: List of (code, label) tuples for services provided by this implementation
        """
        return []
