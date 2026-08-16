import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


_VALID_OUTCOMES = {"success", "rejected", "error"}


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    occurred_at: str
    principal_id: str | None
    key_id: str | None
    event_type: str
    outcome: str
    method: str
    path: str

    def __post_init__(self):
        if not isinstance(self.event_id, str) or not self.event_id.strip():
            raise ValueError("event_id must be a non-empty string.")

        try:
            uuid.UUID(self.event_id)
        except ValueError as error:
            raise ValueError("event_id must be a valid UUID string.") from error

        if not isinstance(self.occurred_at, str) or not self.occurred_at.strip():
            raise ValueError("occurred_at must be a non-empty string.")

        try:
            parsed_occurred_at = datetime.fromisoformat(self.occurred_at)
        except ValueError as error:
            raise ValueError(
                "occurred_at must be a valid ISO-8601 timestamp."
            ) from error

        if parsed_occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware.")

        if parsed_occurred_at.utcoffset() != timedelta(0):
            raise ValueError("occurred_at must be in UTC (zero offset).")

        if self.principal_id is not None and (
            not isinstance(self.principal_id, str) or not self.principal_id.strip()
        ):
            raise ValueError("principal_id must be None or a non-empty string.")

        if self.key_id is not None and (
            not isinstance(self.key_id, str) or not self.key_id.strip()
        ):
            raise ValueError("key_id must be None or a non-empty string.")

        if not isinstance(self.event_type, str) or not self.event_type.strip():
            raise ValueError("event_type must be a non-empty string.")

        if self.outcome not in _VALID_OUTCOMES:
            raise ValueError(
                f"outcome must be one of {sorted(_VALID_OUTCOMES)}, "
                f"got {self.outcome!r}."
            )

        if not isinstance(self.method, str) or not self.method.strip():
            raise ValueError("method must be a non-empty string.")

        if not isinstance(self.path, str) or not self.path.strip():
            raise ValueError("path must be a non-empty string.")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteAuditRepository:
    def __init__(self, database_path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        return sqlite3.connect(self.database_path)

    def _initialize(self):
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    occurred_at TEXT NOT NULL,
                    principal_id TEXT,
                    key_id TEXT,
                    event_type TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    method TEXT NOT NULL,
                    path TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def record_event(
        self,
        *,
        principal_id,
        key_id,
        event_type: str,
        outcome: str,
        method: str,
        path: str,
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            occurred_at=_utc_now_iso(),
            principal_id=principal_id,
            key_id=key_id,
            event_type=event_type,
            outcome=outcome,
            method=method,
            path=path,
        )

        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO audit_events (
                    event_id, occurred_at, principal_id, key_id,
                    event_type, outcome, method, path
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.occurred_at,
                    event.principal_id,
                    event.key_id,
                    event.event_type,
                    event.outcome,
                    event.method,
                    event.path,
                ),
            )
            connection.commit()

        return event
