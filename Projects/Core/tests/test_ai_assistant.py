import unittest

from app.modules.ai.assistant import AIAssistant
from app.modules.ai.providers import AIProviderUnavailable


class FakeProvider:
    provider_name = "fake"
    model = "fake-model"

    def __init__(self, response="generated response"):
        self.response = response
        self.prompts = []
        self.histories = []

    def generate(self, prompt, history=()):
        self.prompts.append(prompt)
        self.histories.append(history)
        return self.response


class AIAssistantResponseTests(unittest.TestCase):
    def test_status_reports_configuration_required_without_provider(self):
        self.assertEqual(AIAssistant().status(), "configuration-required")

    def test_status_reports_online_with_provider(self):
        self.assertEqual(AIAssistant(provider=FakeProvider()).status(), "online")

    def test_status_details_include_no_credentials(self):
        provider = FakeProvider()
        provider.provider_name = "fake"
        provider.model = "fake-model"

        details = AIAssistant(provider=provider).status_details()

        self.assertEqual(
            details,
            {
                "name": "AI Assistant",
                "version": "0.1.0",
                "status": "online",
                "provider": "fake",
                "model": "fake-model",
            },
        )

    def test_delegates_normalized_prompt_to_provider(self):
        provider = FakeProvider()
        assistant = AIAssistant(provider=provider)

        response = assistant.respond("  Explain this  ")

        self.assertEqual(response, "generated response")
        self.assertEqual(provider.prompts, ["Explain this"])

    def test_passes_conversation_history_to_provider(self):
        provider = FakeProvider()
        history = (("user", "Earlier"), ("assistant", "Previous answer"))

        AIAssistant(provider=provider).respond("Next", history=history)

        self.assertEqual(provider.histories, [history])

    def test_default_provider_fails_explicitly(self):
        with self.assertRaisesRegex(
            AIProviderUnavailable, "No AI provider is configured"
        ):
            AIAssistant().respond("hello")

    def test_rejects_blank_prompt_before_calling_provider(self):
        provider = FakeProvider()

        with self.assertRaisesRegex(ValueError, "non-empty"):
            AIAssistant(provider=provider).respond("   ")

        self.assertEqual(provider.prompts, [])

    def test_rejects_empty_provider_response(self):
        with self.assertRaisesRegex(ValueError, "empty response"):
            AIAssistant(provider=FakeProvider(" ")).respond("hello")


if __name__ == "__main__":
    unittest.main()
