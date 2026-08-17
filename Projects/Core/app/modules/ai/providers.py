import json
import os
from json import JSONDecodeError
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class AIProviderUnavailable(RuntimeError):
    pass


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


def provider_from_environment(environ=None) -> AIProvider:
    values = os.environ if environ is None else environ
    api_key = values.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return UnconfiguredAIProvider()

    model = values.get("OPENAI_MODEL", "gpt-5.6-luna").strip()
    return OpenAIResponsesProvider(api_key=api_key, model=model)
