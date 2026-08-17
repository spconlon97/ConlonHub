from app.modules.base import ModuleBase
from app.modules.ai.providers import (
    AIProvider,
    UnconfiguredAIProvider,
    provider_from_environment,
)


class AIAssistant(ModuleBase):
    name = "AI Assistant"
    version = "0.1.0"

    def __init__(self, provider: AIProvider | None = None):
        self.provider = provider or provider_from_environment()

    def start(self):
        return self.status()

    def status(self):
        if isinstance(self.provider, UnconfiguredAIProvider):
            return "configuration-required"
        return "online"

    def status_details(self):
        return {
            "name": self.name,
            "version": self.version,
            "status": self.status(),
            "provider": self.provider.provider_name,
            "model": self.provider.model,
        }

    def respond(self, prompt: str, history=()) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string.")

        response = self.provider.generate(prompt.strip(), history=history)
        if not isinstance(response, str) or not response.strip():
            raise ValueError("AI provider returned an empty response.")
        return response
