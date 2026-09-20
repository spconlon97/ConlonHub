from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable


class CapabilityAccess(str, Enum):
    READ = "read"
    ACTION = "action"


@dataclass(frozen=True)
class Capability:
    name: str
    description: str
    access: CapabilityAccess
    handler: Callable[..., Any]

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Capability name must be a non-empty string.")

        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("Capability description must be a non-empty string.")

        if not callable(self.handler):
            raise ValueError("Capability handler must be callable.")
