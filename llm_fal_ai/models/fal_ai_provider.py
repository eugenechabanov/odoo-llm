import json
import logging
import os

import jsonref
from odoo import models, fields, api, _
from odoo.exceptions import UserError

os.environ.setdefault('FAL_KEY',
                      'acc6b77b-09bb-4925-8cee-56880ed1be87:903fa3da4077aec2b26c8a16b6729a1e')  # Reemplaza con tu API key real

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
        fal_client.api_key = self.api_key
        return fal_client

    # def fal_ai_chat(self, messages, model=None, stream=False, tools=None, **kwargs):
    #     """Implementa la comunicación con la API de chat de fal.ai."""
    #     client = self.fal_ai_get_client()
    #
    #     if not model:
    #         model_obj = self.env["llm.model"].search(
    #             [("provider_id", "=", self.id), ("default", "=", True), ("model_use", "=", "chat")],
    #             limit=1,
    #         )
    #         if not model_obj:
    #             raise UserError(_("No se encontró un modelo de chat predeterminado para el proveedor fal.ai"))
    #         model = model_obj.name
    #
    #     # Preparar parámetros para la llamada a la API
    #     api_params = {}
    #     prompt = ""
    #     if isinstance(messages, str):
    #         prompt = messages
    #     elif isinstance(messages, list) and messages:
    #         # Obtener el último mensaje de usuario
    #         for msg in reversed(messages):
    #             if isinstance(msg, dict) and msg.get("role") == "user":
    #                 prompt = msg.get("content", "")
    #                 break
    #             elif isinstance(msg, str):
    #                 prompt = msg
    #                 break
    #
    #     arguments = {
    #         "prompt": prompt,
    #         "seed": 6252023,
    #         "image_size": "landscape_4_3",
    #         "num_images": 1
    #     }
    #     api_params["arguments"] = arguments
    #     api_params["arguments"].update({k: v for k, v in kwargs.items() if v is not None})
    #
    #     try:
    #
    #         response = client.subscribe(model.name, **api_params)
    #         html_content = "<div class='generated-images'>"
    #         for image in response["images"]:
    #             if "url" in image:
    #                 html_content += f"<img src='{image['url']}' alt='Generate image' class='img-fluid' /><br/>"
    #         html_content += "</div>"
    #
    #         yield {"role": "assistant", "content":html_content }
    #     except Exception as e:
    #         import traceback
    #         traceback.print_exc()
    #         _logger.error("Error al comunicarse con fal.ai: %s", str(e))
    #         raise UserError(_(f"Error en la comunicación con fal.ai: {str(e)}"))
    #
    # def fal_ai_generate_async(self, messages=None, prompt=None, model=None, thread=None, **kwargs):
    #     """Genera texto de forma asíncrona usando el sistema de colas de fal.ai."""
    #     client = self.fal_ai_get_client()
    #
    #     if not model:
    #         model_obj = self.env["llm.model"].search(
    #             [("provider_id", "=", self.id), ("default", "=", True), ("model_use", "=", "chat")],
    #             limit=1,
    #         )
    #         if not model_obj:
    #             raise UserError(_("No se encontró un modelo de chat predeterminado para el proveedor fal.ai"))
    #         model = model_obj.name
    #
    #     # Preparar los mensajes
    #     if messages:
    #         formatted_messages = self.fal_ai_format_messages(messages)
    #     else:
    #         formatted_messages = [{"role": "user", "content": prompt or ""}]
    #
    #     api_params = {
    #         "arguments": {
    #             "messages": formatted_messages
    #         }
    #     }
    #
    #     # Añadir otros parámetros si son necesarios
    #     api_params["arguments"].update({k: v for k, v in kwargs.items() if v is not None})
    #
    #     try:
    #         # Enviar el trabajo a la cola de fal.ai
    #         handler = client.submit(model, **api_params)
    #         request_id = handler.request_id
    #
    #         # Crear el registro de trabajo en Odoo
    #         job_vals = {
    #             'name': f"Fal.ai Job - {model}",
    #             'provider_id': self.id,
    #             'model_id': model_obj.id if model_obj else False,
    #             'thread_id': thread.id if thread else False,
    #             'external_job_id': request_id,
    #             'messages': json.dumps(messages) if messages else "",
    #             'prompt': prompt or "",
    #             'state': 'queued',
    #         }
    #
    #         job = self.env['llm.generate.job'].create(job_vals)
    #         return job
    #
    #     except Exception as e:
    #         _logger.error("Error al enviar trabajo a fal.ai: %s", str(e))
    #         raise UserError(_(f"Error al crear trabajo asíncrono en fal.ai: {str(e)}"))
    #
    # def fal_ai_get_job_status(self, job):
    #     """Verifica el estado de un trabajo asíncrono."""
    #     if not job.external_job_id:
    #         return 'failed'
    #
    #     client = self.fal_ai_get_client()
    #
    #     try:
    #         # Obtenemos el modelo desde el registro de trabajo
    #         model = job.model_id.name if job.model_id else None
    #         if not model:
    #             _logger.error("No se encontró un modelo para el trabajo %s", job.id)
    #             return 'failed'
    #
    #         status_info = client.status(model, job.external_job_id, with_logs=True)
    #         status = status_info.get('status', '')
    #
    #         # Mapear estados de fal.ai a estados de odoo
    #         if status == 'COMPLETED':
    #             return 'completed'
    #         elif status == 'FAILED':
    #             return 'failed'
    #         elif status in ['PENDING', 'RUNNING']:
    #             return 'running'
    #         else:
    #             return 'queued'
    #
    #     except Exception as e:
    #         _logger.error("Error al verificar estado en fal.ai: %s", str(e))
    #         return 'failed'
    #
    # def fal_ai_get_job_result(self, job):
    #     """Obtiene el resultado de un trabajo asíncrono."""
    #     if not job.external_job_id or job.state != 'completed':
    #         return None
    #
    #     client = self.fal_ai_get_client()
    #
    #     try:
    #         # Obtenemos el modelo desde el registro de trabajo
    #         model = job.model_id.name if job.model_id else None
    #         if not model:
    #             _logger.error("No se encontró un modelo para el trabajo %s", job.id)
    #             return None
    #
    #         result = client.result(model, job.external_job_id)
    #
    #         # Transformar el resultado al formato esperado
    #         output = result.get("output", "")
    #
    #         # Si tenemos un resultado de imagen (común en fal.ai), formatearlo correctamente
    #         if "images" in result and result["images"]:
    #             image_urls = [img.get("url", "") for img in result["images"] if "url" in img]
    #             output = "Imágenes generadas:\n" + "\n".join(image_urls)
    #
    #         return output
    #
    #     except Exception as e:
    #         _logger.error("Error al obtener resultado de fal.ai: %s", str(e))
    #         return None

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
