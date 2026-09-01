import json
from types import SimpleNamespace
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


class FakeStream:
    """Minimal stand-in for anthropic's Stream: context manager + iterator."""

    def __init__(self, events):
        self._events = events
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True
        return False

    def __iter__(self):
        return iter(self._events)


class FakeMessages:
    def __init__(self, events):
        self._events = events
        self.create_calls = []
        self.stream_calls = []
        self.streams = []

    def create(self, **params):
        self.create_calls.append(params)
        stream = FakeStream(self._events)
        self.streams.append(stream)
        return stream

    def stream(self, **params):
        # The accumulating helper we must NOT use any more (SPIN11_PROD-5P).
        self.stream_calls.append(params)
        raise AssertionError(
            "messages.stream() must not be used: its per-delta partial JSON "
            "re-parse can raise and kill the whole response"
        )


class FakeClient:
    def __init__(self, events):
        self.messages = FakeMessages(events)


def _start(index, **block):
    return SimpleNamespace(
        type="content_block_start", index=index, content_block=SimpleNamespace(**block)
    )


def _delta(index, **delta):
    return SimpleNamespace(
        type="content_block_delta", index=index, delta=SimpleNamespace(**delta)
    )


def _stop(index):
    return SimpleNamespace(type="content_block_stop", index=index)


@tagged("post_install", "-at_install")
class TestAnthropicStream(TransactionCase):
    """Regression tests for the Anthropic streaming path.

    Sentry SPIN11_PROD-5P: `_anthropic_stream_response` used
    `client.messages.stream()`, the SDK's accumulating helper. That helper
    re-parses the entire accumulated tool-input buffer on every
    `input_json_delta` via `jiter.from_json(..., partial_mode=True)`. When that
    speculative parse raised, the exception propagated out of the `for event in
    stream` loop and killed the whole assistant response, even though this code
    keeps its own buffer and already tolerates malformed JSON.
    """

    def setUp(self):
        super().setUp()
        self.provider = self.env["llm.provider"].create(
            {"name": "Test Anthropic", "service": "anthropic", "api_key": "test-key"}
        )

    def _run(self, events):
        """Run the stream generator against a fake client, return (chunks, client)."""
        client = FakeClient(events)
        with patch.object(
            type(self.provider), "anthropic_get_client", return_value=client
        ):
            chunks = list(
                self.provider._anthropic_stream_response(
                    {"model": "claude-x", "messages": [], "max_tokens": 16}
                )
            )
        return chunks, client

    def test_uses_raw_stream_not_accumulating_helper(self):
        """Must call messages.create(stream=True), never messages.stream()"""
        chunks, client = self._run([_delta(0, text="hi")])

        self.assertEqual(client.messages.stream_calls, [])
        self.assertEqual(len(client.messages.create_calls), 1)
        self.assertTrue(client.messages.create_calls[0]["stream"])
        self.assertEqual(chunks, [{"content": "hi"}])

    def test_text_and_thinking_are_streamed(self):
        """Text and thinking deltas are yielded as they arrive"""
        chunks, _ = self._run(
            [_delta(0, thinking="pondering"), _delta(0, text="a"), _delta(0, text="b")]
        )

        self.assertEqual(
            chunks,
            [{"thinking": "pondering"}, {"content": "a"}, {"content": "b"}],
        )

    def test_tool_call_input_is_accumulated_and_parsed(self):
        """partial_json fragments are joined and parsed once at content_block_stop"""
        events = [
            _start(0, type="tool_use", id="toolu_1", name="odoo_model_inspector"),
            _delta(0, partial_json='{"model": "spin11.ai.email'),
            _delta(0, partial_json='.processor", "field_name_filter": '),
            _delta(0, partial_json='"state"}'),
            _stop(0),
        ]

        chunks, _ = self._run(events)

        self.assertEqual(len(chunks), 1)
        call = chunks[0]["tool_calls"][0]
        self.assertEqual(call["id"], "toolu_1")
        self.assertEqual(call["function"]["name"], "odoo_model_inspector")
        self.assertEqual(
            json.loads(call["function"]["arguments"]),
            {"model": "spin11.ai.email.processor", "field_name_filter": "state"},
        )

    def test_malformed_tool_json_degrades_instead_of_raising(self):
        """SPIN11_PROD-5P: a broken tool-input buffer must not kill the stream"""
        events = [
            _delta(0, text="before"),
            _start(1, type="tool_use", id="toolu_2", name="odoo_model_inspector"),
            # dangling key, never completed - the shape that broke the SDK helper
            _delta(1, partial_json='{"model": "spin11.ai.email.processor", '),
            _delta(1, partial_json='"field_name_filter": '),
            _stop(1),
        ]

        chunks, _ = self._run(events)

        self.assertEqual(chunks[0], {"content": "before"})
        call = chunks[1]["tool_calls"][0]
        self.assertEqual(call["function"]["arguments"], "{}")

    def test_stream_is_closed(self):
        """The stream context manager is exited even on a plain text response"""
        client = FakeClient([_delta(0, text="hi")])
        with patch.object(
            type(self.provider), "anthropic_get_client", return_value=client
        ):
            list(
                self.provider._anthropic_stream_response(
                    {"model": "claude-x", "messages": [], "max_tokens": 16}
                )
            )
        self.assertEqual(len(client.messages.streams), 1)
        self.assertTrue(client.messages.streams[0].closed)
