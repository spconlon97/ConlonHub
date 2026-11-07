from app.modules.base import ModuleBase
from app.modules.ai.orchestration import generate_with_tools
from app.modules.ai.providers import (
    AIProvider,
    UnconfiguredAIProvider,
    provider_from_environment,
)


class AIAssistant(ModuleBase):
    name = "AI Assistant"
    version = "0.2.0"

    def __init__(self, provider: AIProvider | None = None, registry=None):
        self.provider = provider or provider_from_environment()
        if registry is None:
            # Deferred import avoids the builtins -> loader -> assistant cycle.
            from app.core.capabilities.builtin import build_capability_registry
            registry = build_capability_registry()
        self.registry = registry

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

    def respond(self, prompt: str, history=(), principal_id=None, approvals=None) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string.")

        return generate_with_tools(
            self.provider, self.registry, prompt.strip(), history=history,
            approvals=approvals, principal_id=principal_id,
        )
