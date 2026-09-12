import io
import json
import unittest
from urllib.error import HTTPError, URLError

from app.modules.ai.providers import (
    AIProviderUnavailable,
    DEFAULT_MARVIS_SYSTEM_PROMPT,
    OllamaChatProvider,
    provider_from_environment,
)


class FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class RecordingOpener:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def __call__(self, request, timeout):
        self.calls.append((request, timeout))
        return FakeHTTPResponse(self.payload)


class OllamaChatProviderTests(unittest.TestCase):
    def test_sends_chat_request_and_extracts_message_content(self):
        opener = RecordingOpener(
            {"message": {"role": "assistant", "content": "Hello from MARVIS"}}
        )
        provider = OllamaChatProvider(
            model="test-model",
            timeout=12,
            opener=opener,
        )

        result = provider.generate("Hello")

        self.assertEqual(result, "Hello from MARVIS")
        request, timeout = opener.calls[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/chat")
        self.assertEqual(request.method, "POST")
        self.assertEqual(timeout, 12)
        self.assertEqual(
            json.loads(request.data),
            {
                "model": "test-model",
                "messages": [
                    {
                        "role": "system",
                        "content": DEFAULT_MARVIS_SYSTEM_PROMPT,
                    },
                    {"role": "user", "content": "Hello"},
                ],
                "stream": False,
            },
        )
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertIsNone(request.get_header("Authorization"))

    def test_sends_history_before_current_prompt(self):
        opener = RecordingOpener(
            {"message": {"role": "assistant", "content": "ok"}}
        )
        provider = OllamaChatProvider(opener=opener)

        provider.generate(
            "current",
            history=(("user", "earlier"), ("assistant", "answer")),
        )

        request, _timeout = opener.calls[0]
        self.assertEqual(
            json.loads(request.data)["messages"],
            [
                {
                    "role": "system",
                    "content": DEFAULT_MARVIS_SYSTEM_PROMPT,
                },
                {"role": "user", "content": "earlier"},
                {"role": "assistant", "content": "answer"},
                {"role": "user", "content": "current"},
            ],
        )

    def test_transport_errors_are_redacted(self):
        def failing_opener(request, timeout):
            raise URLError("private diagnostic")

        provider = OllamaChatProvider(opener=failing_opener)

        with self.assertRaisesRegex(
            AIProviderUnavailable, "Ollama request failed"
        ) as raised:
            provider.generate("prompt")

        self.assertNotIn("private diagnostic", str(raised.exception))

    def test_http_errors_are_mapped_without_response_body(self):
        def failing_opener(request, timeout):
            raise HTTPError(
                request.full_url,
                404,
                "missing model",
                {},
                io.BytesIO(b'{"error":"private detail"}'),
            )

        with self.assertRaisesRegex(AIProviderUnavailable, "request failed"):
            OllamaChatProvider(opener=failing_opener).generate("prompt")

    def test_missing_message_content_is_unavailable(self):
        provider = OllamaChatProvider(opener=RecordingOpener({"message": {}}))

        with self.assertRaisesRegex(AIProviderUnavailable, "invalid response"):
            provider.generate("prompt")

    def test_blank_message_content_is_unavailable(self):
        provider = OllamaChatProvider(
            opener=RecordingOpener(
                {"message": {"role": "assistant", "content": "   "}}
            )
        )

        with self.assertRaisesRegex(AIProviderUnavailable, "no text"):
            provider.generate("prompt")


class OllamaProviderConfigurationTests(unittest.TestCase):
    def test_ollama_provider_uses_local_defaults(self):
        provider = provider_from_environment({"AI_PROVIDER": "ollama"})

        self.assertIsInstance(provider, OllamaChatProvider)
        self.assertEqual(provider.provider_name, "ollama")
        self.assertEqual(provider.model, "qwen3.5:9b")
        self.assertEqual(provider.endpoint, "http://127.0.0.1:11434/api/chat")

    def test_ollama_model_and_endpoint_can_be_selected(self):
        provider = provider_from_environment(
            {
                "AI_PROVIDER": "ollama",
                "OLLAMA_MODEL": "custom-model",
                "OLLAMA_ENDPOINT": "http://localhost:11434/api/chat",
            }
        )

        self.assertEqual(provider.model, "custom-model")
        self.assertEqual(provider.endpoint, "http://localhost:11434/api/chat")

    def test_unknown_provider_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported AI_PROVIDER"):
            provider_from_environment({"AI_PROVIDER": "unknown"})

    def test_default_identity_preserves_paper_only_boundary(self):
        provider = provider_from_environment({"AI_PROVIDER": "ollama"})

        self.assertIn("MARVIS", provider.system_prompt)
        self.assertIn("Sean Paul", provider.system_prompt)
        self.assertIn("paper trading", provider.system_prompt)
        self.assertIn("Never claim", provider.system_prompt)


if __name__ == "__main__":
    unittest.main()
