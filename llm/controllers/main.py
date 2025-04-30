import json

from odoo import http
from odoo.http import Response, request


class LLMController(http.Controller):
    @http.route('/llm/check_providers', type='http', auth='user')
    def check_providers(self):
        """Check if any provider modules are installed and return the result as JSON."""
        services = request.env['llm.provider']._get_available_services()
        result = {
            'has_providers': len(services) > 0,
            'available_services': services
        }
        return Response(
            json.dumps(result),
            content_type='application/json'
        )