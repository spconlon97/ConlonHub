import json
from dataclasses import dataclass
from json import JSONDecodeError

from app.core.capabilities.models import CapabilityAccess
from app.core.capabilities.registry import (
    CapabilityNotFound,
    CapabilityRegistry,
)


TOOL_REQUEST_PREFIX = "MARVIS_TOOL_REQUEST:"


class ToolExecutionDenied(PermissionError):
    pass


@dataclass(frozen=True)
class ToolRequest:
    capability: str
    arguments: dict

    def __post_init__(self):
        if not isinstance(self.capability, str) or not self.capability.strip():
            raise ValueError("Tool capability must be a non-empty string.")

        if not isinstance(self.arguments, dict):
            raise ValueError("Tool arguments must be an object.")


def parse_tool_request(response: str) -> ToolRequest | None:
    if not isinstance(response, str):
        raise TypeError("response must be a string.")

    stripped = response.strip()

    if not stripped.startswith(TOOL_REQUEST_PREFIX):
        return None

    payload_text = stripped[len(TOOL_REQUEST_PREFIX):].strip()

    try:
        payload = json.loads(payload_text)
    except JSONDecodeError as error:
        raise ValueError("Tool request contains invalid JSON.") from error

    if not isinstance(payload, dict):
        raise ValueError("Tool request payload must be an object.")

    capability = payload.get("capability")
    arguments = payload.get("arguments", {})

    return ToolRequest(
        capability=capability,
        arguments=arguments,
    )


def execute_read_tool(
    registry: CapabilityRegistry,
    request: ToolRequest,
):
    capability = registry.get(request.capability)

    if capability.access != CapabilityAccess.READ:
        raise ToolExecutionDenied(
            f"Capability {capability.name!r} requires approval."
        )

    return registry.execute(
        capability.name,
        **request.arguments,
    )
