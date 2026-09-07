import base64
import json
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


@tagged("post_install", "-at_install", "llm")
class TestAnthropicTranscribe(TransactionCase):
    """Voice dictation transcription (ticket 533).

    Anthropic itself takes no audio, so transcription only works when the
    provider is routed through an OpenAI-compatible gateway that serves
    audio-capable models. These tests pin that contract down.
    """

    def setUp(self):
        super().setUp()
        self.provider = self.env["llm.provider"].create(
            {
                "name": "Test Gateway",
                "service": "anthropic",
                "api_key": "test-key",
                "api_base": "https://gateway.example/api",
                "transcription_model": "google/gemini-3.8-flash",
            }
        )

    def test_transcribe_returns_text(self):
        """A successful call returns just the transcript, stripped."""
        captured = {}

        def fake_post(url, headers=None, data=None, timeout=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["body"] = json.loads(data)
            return FakeResponse(
                payload={"choices": [{"message": {"content": "  Hello Maria  "}}]}
            )

        with patch(
            "odoo.addons.llm_anthropic.models.anthropic_provider.requests.post",
            side_effect=fake_post,
        ):
            text = self.provider.transcribe(b"RIFFfake", "audio/wav")

        self.assertEqual(text, "Hello Maria")
        self.assertEqual(
            captured["url"], "https://gateway.example/api/v1/chat/completions"
        )
        self.assertEqual(captured["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(captured["body"]["model"], "google/gemini-3.8-flash")

        audio_part = captured["body"]["messages"][0]["content"][1]
        self.assertEqual(audio_part["type"], "input_audio")
        self.assertEqual(audio_part["input_audio"]["format"], "wav")
        self.assertEqual(
            base64.b64decode(audio_part["input_audio"]["data"]), b"RIFFfake"
        )

    def test_transcribe_without_api_base_is_refused(self):
        """Talking to Anthropic directly cannot work - say so, don't call out."""
        self.provider.api_base = False
        with patch(
            "odoo.addons.llm_anthropic.models.anthropic_provider.requests.post"
        ) as post:
            with self.assertRaises(UserError):
                self.provider.transcribe(b"RIFFfake", "audio/wav")
        post.assert_not_called()

    def test_transcribe_without_model_is_refused(self):
        """No transcription model configured means dictation is off."""
        self.provider.transcription_model = False
        with patch(
            "odoo.addons.llm_anthropic.models.anthropic_provider.requests.post"
        ) as post:
            with self.assertRaises(UserError):
                self.provider.transcribe(b"RIFFfake", "audio/wav")
        post.assert_not_called()

    def test_transcribe_api_error_raises(self):
        """Gateway errors surface to the user rather than being swallowed."""
        with patch(
            "odoo.addons.llm_anthropic.models.anthropic_provider.requests.post",
            return_value=FakeResponse(status_code=402, text="insufficient credits"),
        ):
            with self.assertRaises(UserError):
                self.provider.transcribe(b"RIFFfake", "audio/wav")

    def test_transcribe_empty_choices_raises(self):
        """A 200 with no result is still a failure, not an empty transcript."""
        with patch(
            "odoo.addons.llm_anthropic.models.anthropic_provider.requests.post",
            return_value=FakeResponse(payload={"choices": []}),
        ):
            with self.assertRaises(UserError):
                self.provider.transcribe(b"RIFFfake", "audio/wav")

    def test_unsupported_audio_format_is_refused(self):
        """Unknown containers are rejected before we ship bytes anywhere."""
        with patch(
            "odoo.addons.llm_anthropic.models.anthropic_provider.requests.post"
        ) as post:
            with self.assertRaises(UserError):
                self.provider.transcribe(b"data", "audio/webm;codecs=opus")
        post.assert_not_called()

    def test_wav_mimetype_variants_accepted(self):
        """Browsers label WAV inconsistently; accept the common spellings."""
        for mimetype in ("audio/wav", "audio/x-wav", "audio/wave", "audio/wav; rate=16000"):
            self.assertEqual(
                self.provider._transcription_audio_format(mimetype), "wav"
            )
