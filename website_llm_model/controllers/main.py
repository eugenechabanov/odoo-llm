from odoo import http
from odoo.http import request


class WebsiteLLMController(http.Controller):
    """Controller for displaying LLM models on website"""

    @http.route(['/llm/models'], type='http', auth="public", website=True)
    def llm_models(self, **kw):
        """Display LLM models categorized by type and provider"""
        # Get active models with prefetched relations
        models = request.env['llm.model'].sudo().search([
            ('active', '=', True)
        ])

        # Get providers with active models - more efficient query
        provider_ids = models.mapped('provider_id').filtered(lambda p: p.active).ids
        providers = request.env['llm.provider'].sudo().browse(provider_ids)

        # Get publishers with active models - use the models we already have
        publisher_ids = models.mapped('publisher_id').ids
        publishers = request.env['llm.publisher'].sudo().browse(publisher_ids)

        # Prepare data for rendering
        model_types = {
            'chat': 'Chat Completion',
            'completion': 'Text Completion',
            'embedding': 'Text Embedding',
            'multimodal': 'Multimodal',
        }

        # Group models by usage type
        models_by_type = {model_type: models.filtered(lambda m: m.model_use == model_type)
                          for model_type in model_types}

        # Group models by provider - more efficient approach
        models_by_provider = {provider.id: models.filtered(lambda m: m.provider_id.id == provider.id)
                              for provider in providers}

        values = {
            'models': models,
            'providers': providers,
            'publishers': publishers,
            'model_types': model_types,
            'models_by_type': models_by_type,
            'models_by_provider': models_by_provider,
            'page_name': 'llm_models',
        }

        return request.render("website_llm_model.models_page", values)
