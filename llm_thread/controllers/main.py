import json
import logging

from odoo import _, api, http
from odoo.exceptions import MissingError, UserError
from odoo.http import Response, request
from odoo.modules.registry import Registry

_logger = logging.getLogger(__name__)

# Dictation clips are short by nature; anything larger is a mistake, and we
# should not ship it to the transcription service.
MAX_TRANSCRIBE_BYTES = 10 * 1024 * 1024


class LLMThreadController(http.Controller):
    @http.route(
        "/llm/thread/<int:thread_id>/update",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=True,
    )
    def llm_thread_update(self, thread_id, **kwargs):
        try:
            thread = request.env["llm.thread"].browse(thread_id)
            if not thread.exists():
                raise MissingError(_("LLM Thread not found."))
            thread.write(kwargs)
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @staticmethod
    def _safe_yield(data_to_yield):
        """Helper generator to yield data safely, handling BrokenPipeError(Disconnected user)."""
        try:
            yield data_to_yield
            return True
        except BrokenPipeError:
            return False
        except Exception:
            return False

    @classmethod
    def _llm_thread_generate(cls, dbname, env, thread_id, user_message_body, **kwargs):
        """Generate LLM responses with streaming and safe yielding."""
        with Registry(dbname).cursor() as cr:
            env = api.Environment(cr, env.uid, env.context)
            llm_thread = env["llm.thread"].browse(int(thread_id))
            if not llm_thread.exists():
                yield from cls._safe_yield(
                    f"data: {json.dumps({'type': 'error', 'error': 'LLM Thread not found.'})}\n\n".encode(),
                )
                return

            client_connected = True
            try:
                for response in llm_thread.generate(user_message_body, **kwargs):
                    json_data = json.dumps(response, default=str)
                    success = yield from cls._safe_yield(
                        f"data: {json_data}\n\n".encode(),
                    )
                    if not success:
                        client_connected = False
                        break

            except GeneratorExit:
                client_connected = False

            except Exception as e:
                _logger.exception(
                    f"Error in llm_thread_generate for thread {thread_id}: {e}",
                )
                # Lock will be automatically released by context manager

                if client_connected:
                    success = yield from cls._safe_yield(
                        f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n".encode(),
                    )
                    if not success:
                        client_connected = False

            finally:
                if client_connected:
                    yield from cls._safe_yield(
                        f"data: {json.dumps({'type': 'done'})}\n\n".encode(),
                    )

    @http.route("/llm/thread/generate", type="http", auth="user", csrf=True)
    def llm_thread_generate(
        self,
        thread_id,
        message=None,
        attachment_ids=None,
        page_context=None,
        **kwargs,
    ):
        headers = {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
        parsed_attachment_ids = []
        if attachment_ids:
            parsed_attachment_ids = [
                int(x) for x in attachment_ids.split(",") if x.strip().isdigit()
            ]
        _logger.info("=== LLM GENERATE: thread_id=%s, page_context=%s, message=%s ===", thread_id, page_context, message[:50] if message else None)
        return Response(
            self._llm_thread_generate(
                request.cr.dbname,
                request.env,
                thread_id,
                message,
                attachment_ids=parsed_attachment_ids,
                page_context=page_context,
                **kwargs,
            ),
            direct_passthrough=True,
            headers=headers,
        )

    @http.route(
        "/llm/thread/<int:thread_id>/transcribe",
        type="http",
        auth="user",
        methods=["POST"],
        csrf=True,
    )
    def llm_thread_transcribe(self, thread_id, audio=None, **kwargs):
        """Turn a recorded dictation into text for the composer.

        Nothing is posted to the thread: the text goes back to the browser so
        the user can read and correct it before deciding to send.
        """
        thread = request.env["llm.thread"].browse(thread_id).exists()
        if not thread:
            raise MissingError(_("LLM Thread not found."))
        # Dictating into a thread is only for users who could post in it.
        thread.check_access("write")

        if audio is None:
            return request.make_json_response(
                {"error": _("No audio was received.")}, status=400
            )

        content = audio.read()
        if not content:
            return request.make_json_response(
                {"error": _("The recording was empty.")}, status=400
            )
        if len(content) > MAX_TRANSCRIBE_BYTES:
            return request.make_json_response(
                {
                    "error": _(
                        "That recording is too long. Please keep dictation "
                        "under a couple of minutes."
                    )
                },
                status=413,
            )

        try:
            text = thread.provider_id.transcribe(
                content, audio.mimetype or "audio/wav"
            )
        except (UserError, NotImplementedError) as e:
            # Configuration problems must be visible, not silently swallowed.
            _logger.warning(
                "Transcription unavailable for thread %s: %s", thread_id, e
            )
            return request.make_json_response(
                {"error": str(e) or _("Voice dictation is not available.")},
                status=400,
            )

        return request.make_json_response({"text": text})
