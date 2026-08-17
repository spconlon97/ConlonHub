import io
import json
import unittest
from urllib.error import HTTPError, URLError

from app.modules.ai.providers import (
    AIProviderUnavailable,
    OpenAIResponsesProvider,
    UnconfiguredAIProvider,
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


class OpenAIResponsesProviderTests(unittest.TestCase):
    def test_sends_responses_request_and_extracts_output_text(self):
        opener = RecordingOpener(
            {
                "output": [
                    {
                        "content": [
                            {"type": "output_text", "text": "Hello from MARVIS"}
                        ]
                    }
                ]
            }
        )
        provider = OpenAIResponsesProvider(
            api_key="secret-value",
            model="test-model",
            timeout=12,
            opener=opener,
        )

        result = provider.generate("Hello")

        self.assertEqual(result, "Hello from MARVIS")
        request, timeout = opener.calls[0]
        self.assertEqual(request.full_url, "https://api.openai.com/v1/responses")
        self.assertEqual(request.method, "POST")
        self.assertEqual(timeout, 12)
        self.assertEqual(
            json.loads(request.data),
            {
                "model": "test-model",
                "input": [{"role": "user", "content": "Hello"}],
            },
        )
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-value")
        self.assertEqual(request.get_header("Content-type"), "application/json")

    def test_combines_multiple_output_text_blocks(self):
        opener = RecordingOpener(
            {
                "output": [
                    {
                        "content": [
                            {"type": "output_text", "text": "first "},
                            {"type": "refusal", "refusal": "ignored"},
                            {"type": "output_text", "text": "second"},
                        ]
                    }
                ]
            }
        )

        result = OpenAIResponsesProvider("key", opener=opener).generate("prompt")

        self.assertEqual(result, "first second")

    def test_sends_history_before_current_prompt(self):
        opener = RecordingOpener(
            {"output": [{"content": [{"type": "output_text", "text": "ok"}]}]}
        )
        provider = OpenAIResponsesProvider("key", opener=opener)

        provider.generate(
            "current",
            history=(("user", "earlier"), ("assistant", "answer")),
        )

        request, _timeout = opener.calls[0]
        self.assertEqual(
            json.loads(request.data)["input"],
            [
                {"role": "user", "content": "earlier"},
                {"role": "assistant", "content": "answer"},
                {"role": "user", "content": "current"},
            ],
        )

    def test_transport_errors_are_redacted(self):
        def failing_opener(request, timeout):
            raise URLError("secret diagnostic")

        provider = OpenAIResponsesProvider("super-secret", opener=failing_opener)

        with self.assertRaisesRegex(
            AIProviderUnavailable, "OpenAI request failed"
        ) as raised:
            provider.generate("prompt")

        self.assertNotIn("super-secret", str(raised.exception))
        self.assertNotIn("secret diagnostic", str(raised.exception))

    def test_http_errors_are_mapped_without_response_body(self):
        def failing_opener(request, timeout):
            raise HTTPError(
                request.full_url,
                401,
                "unauthorized",
                {},
                io.BytesIO(b'{"error":"sensitive"}'),
            )

        with self.assertRaisesRegex(AIProviderUnavailable, "request failed"):
            OpenAIResponsesProvider("key", opener=failing_opener).generate("prompt")

    def test_missing_output_text_is_unavailable(self):
        provider = OpenAIResponsesProvider(
            "key", opener=RecordingOpener({"output": []})
        )

        with self.assertRaisesRegex(AIProviderUnavailable, "no text"):
            provider.generate("prompt")

    def test_malformed_response_shape_is_unavailable(self):
        provider = OpenAIResponsesProvider(
            "key", opener=RecordingOpener({"output": [None]})
        )

        with self.assertRaisesRegex(AIProviderUnavailable, "invalid response"):
            provider.generate("prompt")


class ProviderConfigurationTests(unittest.TestCase):
    def test_missing_key_returns_unconfigured_provider(self):
        provider = provider_from_environment({})

        self.assertIsInstance(provider, UnconfiguredAIProvider)

    def test_key_configures_openai_provider_with_default_model(self):
        provider = provider_from_environment({"OPENAI_API_KEY": "key"})

        self.assertIsInstance(provider, OpenAIResponsesProvider)
        self.assertEqual(provider.provider_name, "openai")
        self.assertEqual(provider.model, "gpt-5.6-luna")

    def test_provider_metadata_and_repr_do_not_expose_key(self):
        provider = OpenAIResponsesProvider("super-secret-key")

        metadata = {
            "provider": provider.provider_name,
            "model": provider.model,
        }

        self.assertNotIn("super-secret-key", repr(provider))
        self.assertNotIn("super-secret-key", repr(metadata))

    def test_model_can_be_selected_from_environment(self):
        provider = provider_from_environment(
            {"OPENAI_API_KEY": "key", "OPENAI_MODEL": "custom-model"}
        )

        self.assertEqual(provider.model, "custom-model")


if __name__ == "__main__":
    unittest.main()
