import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    EXECUTED = "executed"
    FAILED = "failed"


# Statuses reached only through a human decision; they must record when it was made.
_DECIDED_STATUSES = {
    ApprovalStatus.APPROVED,
    ApprovalStatus.REJECTED,
    ApprovalStatus.EXECUTED,
    ApprovalStatus.FAILED,
}

# Statuses reached after an approved request ran; they must record the outcome.
_EXECUTION_STATUSES = {ApprovalStatus.EXECUTED, ApprovalStatus.FAILED}


def canonical_arguments(arguments) -> str:
    if not isinstance(arguments, dict):
        raise ValueError("Approval arguments must be an object.")

    try:
        text = json.dumps(
            arguments, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
    except (TypeError, ValueError) as error:
        raise ValueError("Approval arguments must be JSON-serializable.") from error

    # json.dumps silently converts non-string keys and tuples; a lossless
    # round trip guarantees the approved arguments are exactly what runs.
    if json.loads(text) != arguments:
        raise ValueError("Approval arguments must be plain JSON values.")

    return text


def arguments_digest(arguments) -> str:
    return hashlib.sha256(canonical_arguments(arguments).encode("utf-8")).hexdigest()


def _require_text(value, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string.")


def _parse_utc(value, field: str) -> datetime:
    _require_text(value, field)

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{field} must be a valid ISO-8601 timestamp.") from error

    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be a UTC timestamp.")

    return parsed


@dataclass(frozen=True)
class ApprovalRequest:
    request_id: str
    principal_id: str
    capability: str
    arguments: dict
    arguments_digest: str
    summary: str
    status: ApprovalStatus
    created_at: str
    expires_at: str
    decided_at: str | None = None
    outcome: str | None = None

    def __post_init__(self):
        _require_text(self.request_id, "request_id")
        try:
            uuid.UUID(self.request_id)
        except ValueError as error:
            raise ValueError("request_id must be a valid UUID string.") from error

        _require_text(self.principal_id, "principal_id")
        _require_text(self.capability, "capability")
        _require_text(self.summary, "summary")

        if self.arguments_digest != arguments_digest(self.arguments):
            raise ValueError("arguments_digest does not match arguments.")

        if not isinstance(self.status, ApprovalStatus):
            raise ValueError("status must be an ApprovalStatus.")

        created_at = _parse_utc(self.created_at, "created_at")
        expires_at = _parse_utc(self.expires_at, "expires_at")
        if expires_at <= created_at:
            raise ValueError("expires_at must be after created_at.")

        if self.status in _DECIDED_STATUSES:
            _parse_utc(self.decided_at, "decided_at")
        elif self.decided_at is not None:
            raise ValueError(f"A {self.status.value} request has no decision time.")

        if self.status in _EXECUTION_STATUSES:
            _require_text(self.outcome, "outcome")
        elif self.outcome is not None:
            raise ValueError(f"A {self.status.value} request has no outcome.")
