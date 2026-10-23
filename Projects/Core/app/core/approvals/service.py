import json

from app.core.approvals.models import ApprovalRequest
from app.core.approvals.repository import MAX_OUTCOME_LENGTH, SqliteApprovalRepository
from app.core.capabilities.registry import (
    CapabilityNotFound,
    CapabilityRegistry,
    CapabilityRequiresApproval,
)


_UNSAFE_OUTCOME = "Approval could not be executed safely."
_FAILED_OUTCOME = "Execution failed."


def _describe(result) -> str:
    if result is None:
        return "Executed."
    try:
        text = json.dumps(result, sort_keys=True, default=str, allow_nan=False)
    except (TypeError, ValueError):
        return "Executed."
    return text[:MAX_OUTCOME_LENGTH]


def approve_and_execute(
    repository: SqliteApprovalRepository,
    registry: CapabilityRegistry,
    request_id: str,
    principal_id: str,
) -> ApprovalRequest:
    """Approve, run once, and record the outcome.

    The decision is committed before the action runs. If the process stops
    between the two, the request stays approved and is never run again:
    an action happens at most once.
    """
    approved = repository.decide(request_id, principal_id, approve=True)

    try:
        result = registry.execute_approved(approved)
    except (CapabilityRequiresApproval, CapabilityNotFound):
        return repository.mark_failed(request_id, principal_id, _UNSAFE_OUTCOME)
    except ValueError as error:
        # Capability validation errors (limits, cash, positions) are meant for the user.
        message = str(error).strip() or _FAILED_OUTCOME
        return repository.mark_failed(request_id, principal_id, message[:MAX_OUTCOME_LENGTH])
    except Exception:
        return repository.mark_failed(request_id, principal_id, _FAILED_OUTCOME)

    return repository.mark_executed(request_id, principal_id, _describe(result))


def reject(
    repository: SqliteApprovalRepository,
    request_id: str,
    principal_id: str,
) -> ApprovalRequest:
    return repository.decide(request_id, principal_id, approve=False)
