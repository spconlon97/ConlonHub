import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.approvals.models import (
    ApprovalRequest,
    ApprovalStatus,
    arguments_digest,
    canonical_arguments,
)
from app.core.database import migrate_database


DEFAULT_APPROVAL_TTL = timedelta(minutes=15)

_COLUMNS = (
    "request_id, principal_id, capability, arguments, arguments_digest, "
    "summary, status, created_at, expires_at, decided_at"
)


class ApprovalNotFound(LookupError):
    pass


class ApprovalNotPending(ValueError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(moment: datetime) -> str:
    # Fixed-width UTC timestamps compare correctly as strings in SQL.
    return moment.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _from_row(row) -> ApprovalRequest:
    return ApprovalRequest(
        request_id=row[0],
        principal_id=row[1],
        capability=row[2],
        arguments=json.loads(row[3]),
        arguments_digest=row[4],
        summary=row[5],
        status=ApprovalStatus(row[6]),
        created_at=row[7],
        expires_at=row[8],
        decided_at=row[9],
    )


class SqliteApprovalRepository:
    def __init__(self, database_path, clock=_utc_now):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        self._initialize()

    def _connect(self):
        return sqlite3.connect(self.database_path)

    def _initialize(self):
        migrate_database(self.database_path, "approvals")

    def _now(self) -> str:
        return _timestamp(self._clock())

    def _expire_stale(self, connection, now: str, **scope) -> None:
        clauses = ["status = 'pending'", "expires_at <= ?"]
        parameters = [now]
        for column, value in scope.items():
            clauses.append(f"{column} = ?")
            parameters.append(value)

        connection.execute(
            "UPDATE approval_requests SET status = 'expired' WHERE "
            + " AND ".join(clauses),
            parameters,
        )

    def _select(self, connection, request_id: str, principal_id: str):
        return connection.execute(
            f"SELECT {_COLUMNS} FROM approval_requests "
            "WHERE request_id = ? AND principal_id = ?",
            (request_id, principal_id),
        ).fetchone()

    def create(
        self,
        *,
        principal_id: str,
        capability: str,
        arguments: dict,
        summary: str,
        ttl: timedelta = DEFAULT_APPROVAL_TTL,
    ) -> ApprovalRequest:
        if not isinstance(ttl, timedelta) or ttl <= timedelta(0):
            raise ValueError("ttl must be a positive timedelta.")

        created = self._clock()
        stored_arguments = canonical_arguments(arguments)
        request = ApprovalRequest(
            request_id=str(uuid.uuid4()),
            principal_id=principal_id,
            capability=capability,
            arguments=json.loads(stored_arguments),
            arguments_digest=arguments_digest(arguments),
            summary=summary,
            status=ApprovalStatus.PENDING,
            created_at=_timestamp(created),
            expires_at=_timestamp(created + ttl),
        )

        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    f"INSERT INTO approval_requests ({_COLUMNS}) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        request.request_id,
                        request.principal_id,
                        request.capability,
                        stored_arguments,
                        request.arguments_digest,
                        request.summary,
                        request.status.value,
                        request.created_at,
                        request.expires_at,
                        None,
                    ),
                )

        return request

    def get(self, request_id: str, principal_id: str) -> ApprovalRequest:
        with closing(self._connect()) as connection:
            with connection:
                self._expire_stale(
                    connection, self._now(),
                    request_id=request_id, principal_id=principal_id,
                )
                row = self._select(connection, request_id, principal_id)

        if row is None:
            raise ApprovalNotFound(request_id)
        return _from_row(row)

    def list_pending(self, principal_id: str) -> tuple[ApprovalRequest, ...]:
        with closing(self._connect()) as connection:
            with connection:
                self._expire_stale(connection, self._now(), principal_id=principal_id)
                rows = connection.execute(
                    f"SELECT {_COLUMNS} FROM approval_requests "
                    "WHERE principal_id = ? AND status = 'pending' "
                    "ORDER BY created_at DESC, request_id",
                    (principal_id,),
                ).fetchall()

        return tuple(_from_row(row) for row in rows)

    def decide(
        self, request_id: str, principal_id: str, *, approve: bool
    ) -> ApprovalRequest:
        if type(approve) is not bool:
            raise TypeError("approve must be a bool.")

        status = ApprovalStatus.APPROVED if approve else ApprovalStatus.REJECTED
        now = self._now()

        with closing(self._connect()) as connection:
            with connection:
                # Lock first so two deciders cannot both see the request as pending.
                connection.execute("BEGIN IMMEDIATE")
                self._expire_stale(
                    connection, now,
                    request_id=request_id, principal_id=principal_id,
                )
                updated = connection.execute(
                    "UPDATE approval_requests SET status = ?, decided_at = ? "
                    "WHERE request_id = ? AND principal_id = ? "
                    "AND status = 'pending' AND expires_at > ?",
                    (status.value, now, request_id, principal_id, now),
                ).rowcount
                row = self._select(connection, request_id, principal_id)

        # Raise only after commit so an expiry discovered here is persisted.
        if row is None:
            raise ApprovalNotFound(request_id)
        request = _from_row(row)
        if updated != 1:
            raise ApprovalNotPending(
                f"Approval request is {request.status.value}, not pending."
            )
        return request
