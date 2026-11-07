from app.core.approvals.models import ApprovalRequest, ApprovalStatus, arguments_digest
from app.core.capabilities.models import Capability, CapabilityAccess


class CapabilityNotFound(KeyError):
    pass


class CapabilityAlreadyRegistered(ValueError):
    pass


class CapabilityRequiresApproval(PermissionError):
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
        if capability.access != CapabilityAccess.READ:
            raise CapabilityRequiresApproval(
                f"Capability {capability.name!r} requires an approved request."
            )
        return capability.handler(**arguments)

    def execute_approved(self, request: ApprovalRequest):
        """The only path that runs an ACTION: re-checks the approval first."""
        if not isinstance(request, ApprovalRequest):
            raise TypeError("request must be an ApprovalRequest.")

        if request.status != ApprovalStatus.APPROVED:
            raise CapabilityRequiresApproval("Approval request is not approved.")

        capability = self.get(request.capability)
        if capability.access != CapabilityAccess.ACTION:
            raise CapabilityRequiresApproval("Approved capability is no longer an ACTION.")

        # The record validates its digest when built; re-check in case it was altered.
        if arguments_digest(request.arguments) != request.arguments_digest:
            raise CapabilityRequiresApproval("Approved arguments have changed.")

        return capability.handler(**request.arguments)
