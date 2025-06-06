import json
import logging
import os

import jsonref
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import fal_client
except ImportError:
    _logger.warning("No se pudo importar fal_client. Instala el paquete con pip: pip install fal_client")
    fal_client = None


class LLMProvider(models.Model):
    _inherit = "llm.provider"

    def fal_ai_supports_async_generation(self, default=None):
        return True

    @api.model
    def _get_available_services(self):
        services = super()._get_available_services()
        services.append(("fal_ai", "Fal.ai"))
        return services

    def fal_ai_get_client(self):
        """Inicializa y devuelve el cliente de fal.ai."""
        if not fal_client:
            raise UserError(_("El paquete fal_client no está instalado. Instálalo con pip: pip install fal_client"))

        # fal.ai usa variables de entorno para la API_KEY, pero también podemos configurarla programáticamente
        os.environ.setdefault('FAL_KEY',self.api_key)
        return fal_client

    def fal_ai_models(self, model_id=None):
        """Obtiene la lista de modelos disponibles en fal.ai."""
        # Actualmente fal.ai no proporciona un endpoint para listar modelos
        # Implementación con modelos conocidos
        models = [
            {"id": "fal-ai/flux/dev", "name": "fal-ai/flux/dev", "description": "Modelo para generación de imágenes",
             "capabilities": "multimodal"},
            {"id": "fal-ai/lcm", "name": "fal-ai/lcm", "description": "Latent Consistency Model",
             "capabilities": "multimodal"}
            # Añadir más modelos según disponibilidad en fal.ai
        ]

        return models

    def fal_ai_generate_io_schema(self, model_record):
        """Genera los esquemas de entrada y salida para modelos de generación de imágenes fal.ai."""
        model_record.input_schema = {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Descripción de la imagen a generar",
                    "title": "Prompt"
                },
                "negative_prompt": {
                    "type": "string",
                    "description": "Elementos a evitar en la imagen generada",
                    "title": "Prompt Negativo",
                    "default": ""
                },
                "image_size": {
                    "type": "string",
                    "description": "Tamaño de la imagen generada",
                    "enum": ["square", "portrait", "landscape", "landscape_16_9", "landscape_4_3"],
                    "default": "square",
                    "title": "Tamaño de imagen"
                },
                "num_images": {
                    "type": "integer",
                    "description": "Número de imágenes a generar",
                    "minimum": 1,
                    "maximum": 4,
                    "default": 1,
                    "title": "Cantidad de imágenes"
                },
                "seed": {
                    "type": "integer",
                    "description": "Semilla para reproducibilidad",
                    "default": 42,
                    "title": "Semilla"
                }
            },
            "required": ["prompt"]
        }

        model_record.output_schema = {
            "type": "array",
            "items": {
                "type": "string",
                "format": "uri"
            },
            "title": "Output"
        }

    def fal_ai_generate_media(self, inputs, model_record=None, stream=False):
        """Generate media content using this provider"""
        # Get full model name including version if specified
        model_name = model_obj = self.env["llm.model"].search(
            [("provider_id", "=", self.id), ("default", "=", True), ("model_use", "=", "multimodal")],
            limit=1,
        )
        if not model_name:
            model_name = model_record.name

        if not model_name:
            raise ValueError("Model name is required")

        # Run the model
        result = self.client.subscribe(model_name, arguments=inputs)
        urls = self._fal_ai_extract_urls_from_result(result)
        yield {"content": urls}

    def fal_ai_format_generation_response(self, raw_response, output_schema):
        """Format the raw generation response according to the output processing config

        Args:
            raw_response: The raw response from the provider (e.g., fal_ai client.run()).
                          Typically a list of URLs or a single URL string for images.
            output_schema (dict): Schema of the output.

        Returns:
            list: A list of strings (e.g., URLs) extracted from the raw_response.
                  Returns an empty list if no suitable strings are found or
                  if the raw_response format is unexpected.
        """

        extracted_strings = []

        # output_schema example: {"type": "array", "items": {"type": "string", "format": "uri"}}
        # This implies the raw_response should ideally be a list of strings, or a single string.

        if isinstance(raw_response, list):
            for item in raw_response:
                if isinstance(item, str):
                    extracted_strings.append(item)
                else:
                    # Log if an item in the list is not a string, but continue processing
                    _logger.warning(
                        f"Replicate: Item in raw_response list is not a string: {item} (type: {type(item)}). Output schema: {output_schema}"
                    )
        elif isinstance(raw_response, str):
            # If the raw_response is a single string, assume it's the URL/data itself.
            extracted_strings.append(raw_response)
        elif raw_response is None:
            _logger.info(
                f"Replicate: Raw response is None for schema {output_schema}. Returning empty list."
            )
        else:
            _logger.warning(
                f"Replicate: Unexpected raw_response type: {type(raw_response)}. Full response: {raw_response}. Output schema: {output_schema}"
            )
            # For now, we return an empty list. More sophisticated parsing based on
            # output_schema could be added here if needed for complex objects.

        _logger.info(f"Replicate: Extracted strings: {extracted_strings}")
        return extracted_strings


    def _fal_ai_extract_urls_from_result(self, result):
        """Extract URLs from fal_ai result, handling FileOutput objects and other formats"""
        urls = []

        if result is None:
            return urls
        # Example of fal_ai result: {'has_nsfw_concepts': [False], 'images': [{'content_type': 'image/png', 'height': 768, 'url': 'https://v3.fal.media/files/zebra/3Sa_l4tFKlX4-bai5Z0ST.png', 'width': 1024}], 'prompt': 'un gato azul', 'seed': 6252023, 'timings': {'inference': 2.1407407799270004}}
        if isinstance(result, list):
            # If result is a list, extract URLs from each item
            for item in result:
                url = self._fal_ai_extract_single_url(item)
                if url:
                    urls.append(url)

        elif isinstance(result, dict):
            # If result is a dictionary, check for 'images' key or other URL fields
            if "images" in result:
                for item in result["images"]:
                    url = self._fal_ai_extract_single_url(item)
                    if url:
                        urls.append(url)
            else:
                # Check for other potential URL fields in the dictionary
                url = self._fal_ai_extract_single_url(result)
                if url:
                    urls.append(url)

        else:
            # If result is a single item (not a list or dict), extract URL directly
            url = self._fal_ai_extract_single_url(result)
            if url:
                urls.append(url)

        return urls

    def _fal_ai_extract_single_url(self, item):
        """Extract URL from a single result item"""
        if isinstance(item, dict):
            if "url" in item:
                return item["url"]
            elif "content" in item and isinstance(item["content"], str):
                return item["content"]
