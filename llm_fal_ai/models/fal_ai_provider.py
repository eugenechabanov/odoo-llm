import json
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import os

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
        os.environ.setdefault('FAL_KEY', self.api_key)
        return fal_client

    def fal_ai_chat(self, messages, model=None, stream=False, tools=None, **kwargs):
        """Implementa la comunicación con la API de chat de fal.ai."""
        client = self.fal_ai_get_client()

        if not model:
            model_obj = self.env["llm.model"].search(
                [("provider_id", "=", self.id), ("default", "=", True), ("model_use", "=", "chat")],
                limit=1,
            )
            if not model_obj:
                raise UserError(_("No se encontró un modelo de chat predeterminado para el proveedor fal.ai"))
            model = model_obj.name

        # Preparar parámetros para la llamada a la API
        api_params = {}
        prompt = ""
        if isinstance(messages, str):
            prompt = messages
        elif isinstance(messages, list) and messages:
            # Obtener el último mensaje de usuario
            for msg in reversed(messages):
                if isinstance(msg, dict) and msg.get("role") == "user":
                    prompt = msg.get("content", "")
                    break
                elif isinstance(msg, str):
                    prompt = msg
                    break

        arguments = {
            "prompt": prompt,
            "seed": 6252023,
            "image_size": "landscape_4_3",
            "num_images": 1
        }
        api_params["arguments"] = arguments
        api_params["arguments"].update({k: v for k, v in kwargs.items() if v is not None})

        try:

            response = client.subscribe(model.name, **api_params)
            html_content = "<div class='generated-images'>"
            for image in response["images"]:
                if "url" in image:
                    html_content += f"<img src='{image['url']}' alt='Generate image' class='img-fluid' /><br/>"
            html_content += "</div>"

            yield {"role": "assistant", "content":html_content }
        except Exception as e:
            import traceback
            traceback.print_exc()
            _logger.error("Error al comunicarse con fal.ai: %s", str(e))
            raise UserError(_(f"Error en la comunicación con fal.ai: {str(e)}"))

    def fal_ai_generate_async(self, messages=None, prompt=None, model=None, thread=None, **kwargs):
        """Genera texto de forma asíncrona usando el sistema de colas de fal.ai."""
        client = self.fal_ai_get_client()

        if not model:
            model_obj = self.env["llm.model"].search(
                [("provider_id", "=", self.id), ("default", "=", True), ("model_use", "=", "chat")],
                limit=1,
            )
            if not model_obj:
                raise UserError(_("No se encontró un modelo de chat predeterminado para el proveedor fal.ai"))
            model = model_obj.name

        # Preparar los mensajes
        if messages:
            formatted_messages = self.fal_ai_format_messages(messages)
        else:
            formatted_messages = [{"role": "user", "content": prompt or ""}]

        api_params = {
            "arguments": {
                "messages": formatted_messages
            }
        }

        # Añadir otros parámetros si son necesarios
        api_params["arguments"].update({k: v for k, v in kwargs.items() if v is not None})

        try:
            # Enviar el trabajo a la cola de fal.ai
            handler = client.submit(model, **api_params)
            request_id = handler.request_id

            # Crear el registro de trabajo en Odoo
            job_vals = {
                'name': f"Fal.ai Job - {model}",
                'provider_id': self.id,
                'model_id': model_obj.id if model_obj else False,
                'thread_id': thread.id if thread else False,
                'external_job_id': request_id,
                'messages': json.dumps(messages) if messages else "",
                'prompt': prompt or "",
                'state': 'queued',
            }

            job = self.env['llm.generate.job'].create(job_vals)
            return job

        except Exception as e:
            _logger.error("Error al enviar trabajo a fal.ai: %s", str(e))
            raise UserError(_(f"Error al crear trabajo asíncrono en fal.ai: {str(e)}"))

    def fal_ai_get_job_status(self, job):
        """Verifica el estado de un trabajo asíncrono."""
        if not job.external_job_id:
            return 'failed'

        client = self.fal_ai_get_client()

        try:
            # Obtenemos el modelo desde el registro de trabajo
            model = job.model_id.name if job.model_id else None
            if not model:
                _logger.error("No se encontró un modelo para el trabajo %s", job.id)
                return 'failed'

            status_info = client.status(model, job.external_job_id, with_logs=True)
            status = status_info.get('status', '')

            # Mapear estados de fal.ai a estados de odoo
            if status == 'COMPLETED':
                return 'completed'
            elif status == 'FAILED':
                return 'failed'
            elif status in ['PENDING', 'RUNNING']:
                return 'running'
            else:
                return 'queued'

        except Exception as e:
            _logger.error("Error al verificar estado en fal.ai: %s", str(e))
            return 'failed'

    def fal_ai_get_job_result(self, job):
        """Obtiene el resultado de un trabajo asíncrono."""
        if not job.external_job_id or job.state != 'completed':
            return None

        client = self.fal_ai_get_client()

        try:
            # Obtenemos el modelo desde el registro de trabajo
            model = job.model_id.name if job.model_id else None
            if not model:
                _logger.error("No se encontró un modelo para el trabajo %s", job.id)
                return None

            result = client.result(model, job.external_job_id)

            # Transformar el resultado al formato esperado
            output = result.get("output", "")

            # Si tenemos un resultado de imagen (común en fal.ai), formatearlo correctamente
            if "images" in result and result["images"]:
                image_urls = [img.get("url", "") for img in result["images"] if "url" in img]
                output = "Imágenes generadas:\n" + "\n".join(image_urls)

            return output

        except Exception as e:
            _logger.error("Error al obtener resultado de fal.ai: %s", str(e))
            return None

    def fal_ai_models(self, model_id=None):
        """Obtiene la lista de modelos disponibles en fal.ai."""
        # Actualmente fal.ai no proporciona un endpoint para listar modelos
        # Implementación con modelos conocidos
        models = [
            {"id": "fal-ai/flux/dev", "name": "Flux", "description": "Modelo para generación de imágenes"},
            {"id": "fal-ai/lcm", "name": "LCM", "description": "Latent Consistency Model"},
            # Añadir más modelos según disponibilidad en fal.ai
        ]

        return models

    def fal_ai_format_messages(self, messages):
        """Formatea los mensajes para la API de fal.ai."""
        formatted_messages = []

        # Si messages es un string, conviértelo en un mensaje de usuario
        if isinstance(messages, str):
            formatted_messages.append({
                "role": "user",
                "content": messages
            })
            return formatted_messages

        # Procesar cada mensaje
        for message in messages:
            if isinstance(message, dict):
                # Si es un diccionario, usar get()
                formatted_message = {
                    "role": message.get("role", "user"),
                    "content": message.get("content", "")
                }
            elif isinstance(message, str):
                # Si es string, asumir que es mensaje de usuario
                formatted_message = {
                    "role": "user",
                    "content": message
                }
            else:
                # Para otros tipos, convertir a string
                formatted_message = {
                    "role": "user",
                    "content": str(message)
                }

            formatted_messages.append(formatted_message)

        return formatted_messages

    def fal_ai_format_tools(self, tools):
        """Formatea las herramientas/funciones para la API de fal.ai si es soportado."""
        return tools
