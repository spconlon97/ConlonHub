from app.core.capabilities.models import Capability


class CapabilityNotFound(KeyError):
    pass


class CapabilityAlreadyRegistered(ValueError):
    pass


class CapabilityRegistry:
    def __init__(self):
        self._capabilities: dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        if not isinstance(capability, Capability):
            raise TypeError("capability must be a Capability.")

        if capability.name in self._capabilities:
            raise CapabilityAlreadyRegistered(
                f"Capability {capability.name!r} is already registered."
            )

        self._capabilities[capability.name] = capability

    def get(self, name: str) -> Capability:
        try:
            return self._capabilities[name]
        except KeyError as error:
            raise CapabilityNotFound(name) from error

    def list(self) -> tuple[Capability, ...]:
        return tuple(
            self._capabilities[name]
            for name in sorted(self._capabilities)
        )

    def execute(self, name: str, **arguments):
        capability = self.get(name)
        return capability.handler(**arguments)
