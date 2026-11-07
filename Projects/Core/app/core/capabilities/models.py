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
    # ACTION only: turns the arguments into the text a human approves.
    summarize: Callable[..., str] | None = None

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Capability name must be a non-empty string.")

        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("Capability description must be a non-empty string.")

        if not callable(self.handler):
            raise ValueError("Capability handler must be callable.")

        if self.access == CapabilityAccess.ACTION and not callable(self.summarize):
            raise ValueError("ACTION capabilities require a callable summarize.")

        if self.access == CapabilityAccess.READ and self.summarize is not None:
            raise ValueError("READ capabilities must not define summarize.")
