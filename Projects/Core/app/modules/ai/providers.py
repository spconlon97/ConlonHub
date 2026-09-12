import json
import os
from json import JSONDecodeError
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class AIProviderUnavailable(RuntimeError):
    pass


DEFAULT_MARVIS_SYSTEM_PROMPT = (
    "You are MARVIS, the local AI assistant for Sean Paul's Conlon Hub. "
    "Identify yourself as MARVIS. Sean Paul is the owner and operator who set up "
    "this system. You run locally through Ollama using the configured model. "
    "Be concise, accurate, practical, and honest about your capabilities. "
    "Conlon Hub's Trading Bot is restricted to paper trading and simulated data. "
    "Never claim that you can place live trades or access live markets."
)


class AIProvider(Protocol):
    provider_name: str
    model: str | None

    def generate(self, prompt: str, history=()) -> str:
        pass


class UnconfiguredAIProvider:
    provider_name = "unconfigured"
    model = None

    def generate(self, prompt: str, history=()) -> str:
        raise AIProviderUnavailable("No AI provider is configured.")


class OpenAIResponsesProvider:
    provider_name = "openai"
    endpoint = "https://api.openai.com/v1/responses"

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5.6-luna",
        timeout: float = 60.0,
        opener=urlopen,
    ):
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("api_key must be a non-empty string.")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty string.")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero.")

        self._api_key = api_key.strip()
        self.model = model.strip()
        self.timeout = timeout
        self._opener = opener

    def generate(self, prompt: str, history=()) -> str:
        messages = [
            {"role": role, "content": content}
            for role, content in history
        ]
        messages.append({"role": "user", "content": prompt})
        body = json.dumps({"model": self.model, "input": messages}).encode()
        request = Request(
            self.endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with self._opener(request, timeout=self.timeout) as response:
                payload = json.loads(response.read())
        except (
            HTTPError,
            URLError,
            TimeoutError,
            JSONDecodeError,
            UnicodeDecodeError,
            OSError,
        ) as error:
            raise AIProviderUnavailable("OpenAI request failed.") from error

        try:
            text_parts = [
                content["text"]
                for output in payload.get("output", [])
                for content in output.get("content", [])
                if content.get("type") == "output_text"
                and isinstance(content.get("text"), str)
            ]
        except (AttributeError, KeyError, TypeError) as error:
            raise AIProviderUnavailable("OpenAI returned an invalid response.") from error
        response_text = "".join(text_parts).strip()
        if not response_text:
            raise AIProviderUnavailable("OpenAI returned no text response.")
        return response_text


class OllamaChatProvider:
    provider_name = "ollama"
    default_endpoint = "http://127.0.0.1:11434/api/chat"

    def __init__(
        self,
        model: str = "qwen3.5:9b",
        endpoint: str = default_endpoint,
        system_prompt: str = DEFAULT_MARVIS_SYSTEM_PROMPT,
        timeout: float = 120.0,
        opener=urlopen,
    ):
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty string.")
        if not isinstance(endpoint, str) or not endpoint.strip():
            raise ValueError("endpoint must be a non-empty string.")
        if not isinstance(system_prompt, str) or not system_prompt.strip():
            raise ValueError("system_prompt must be a non-empty string.")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero.")

        self.model = model.strip()
        self.endpoint = endpoint.strip()
        self.system_prompt = system_prompt.strip()
        self.timeout = timeout
        self._opener = opener

    def generate(self, prompt: str, history=()) -> str:
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(
            {"role": role, "content": content}
            for role, content in history
        )
        messages.append({"role": "user", "content": prompt})
        body = json.dumps(
            {
                "model": self.model,
                "messages": messages,
                "stream": False,
            }
        ).encode()
        request = Request(
            self.endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with self._opener(request, timeout=self.timeout) as response:
                payload = json.loads(response.read())
        except (
            HTTPError,
            URLError,
            TimeoutError,
            JSONDecodeError,
            UnicodeDecodeError,
            OSError,
        ) as error:
            raise AIProviderUnavailable("Ollama request failed.") from error

        try:
            response_text = payload["message"]["content"].strip()
        except (AttributeError, KeyError, TypeError) as error:
            raise AIProviderUnavailable("Ollama returned an invalid response.") from error
        if not response_text:
            raise AIProviderUnavailable("Ollama returned no text response.")
        return response_text


def provider_from_environment(environ=None) -> AIProvider:
    values = os.environ if environ is None else environ
    provider_name = values.get("AI_PROVIDER", "").strip().lower()

    if provider_name == "ollama":
        model = values.get("OLLAMA_MODEL", "qwen3.5:9b").strip()
        endpoint = values.get(
            "OLLAMA_ENDPOINT", OllamaChatProvider.default_endpoint
        ).strip()
        return OllamaChatProvider(model=model, endpoint=endpoint)

    if provider_name not in ("", "openai"):
        raise ValueError(f"Unsupported AI_PROVIDER: {provider_name!r}.")

    api_key = values.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return UnconfiguredAIProvider()

    model = values.get("OPENAI_MODEL", "gpt-5.6-luna").strip()
    return OpenAIResponsesProvider(api_key=api_key, model=model)
