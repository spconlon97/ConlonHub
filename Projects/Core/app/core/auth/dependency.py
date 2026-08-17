import logging
import sqlite3
from pathlib import Path

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth.audit import SqliteAuditRepository
from app.core.auth.credentials import parse_api_key, verify_api_key
from app.core.auth.principal import Principal
from app.core.auth.repository import SqliteAuthRepository


_bearer_scheme = HTTPBearer(auto_error=True)
_logger = logging.getLogger(__name__)

_AUDIT_FAILURE_LOG_MESSAGE = "Security audit event could not be persisted."


def get_auth_repository() -> SqliteAuthRepository:
    database_path = (
        Path(__file__).resolve().parents[5] / "Databases" / "core_auth.db"
    )
    return SqliteAuthRepository(database_path)


def get_audit_repository() -> SqliteAuditRepository | None:
    try:
        database_path = (
            Path(__file__).resolve().parents[5] / "Databases" / "core_audit.db"
        )
        return SqliteAuditRepository(database_path)
    except (OSError, sqlite3.Error):
        _logger.warning(_AUDIT_FAILURE_LOG_MESSAGE)
        return None


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _internal_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
    )


def _record_event_safely(
    audit: SqliteAuditRepository | None,
    *,
    principal_id,
    key_id,
    outcome: str,
    request: Request,
) -> None:
    if audit is None:
        return

    try:
        audit.record_event(
            principal_id=principal_id,
            key_id=key_id,
            event_type="auth.authenticate",
            outcome=outcome,
            method=request.method,
            path=request.url.path,
        )
    except (ValueError, sqlite3.Error):
        _logger.warning(_AUDIT_FAILURE_LOG_MESSAGE)


def require_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    repository: SqliteAuthRepository = Depends(get_auth_repository),
    audit: SqliteAuditRepository | None = Depends(get_audit_repository),
) -> Principal:
    try:
        parsed = parse_api_key(credentials.credentials)
    except ValueError as error:
        _record_event_safely(
            audit, principal_id=None, key_id=None, outcome="rejected", request=request
        )
        raise _unauthorized() from error

    try:
        stored = repository.find_credential_by_key_id(parsed.key_id)
    except ValueError as error:
        # A row WAS located by an exact key_id match; only its other
        # columns (scheme/salt/digest) failed reconstruction. The key_id
        # is therefore confirmed to exist in storage, independent of the
        # corruption, so it is safe to record.
        _record_event_safely(
            audit,
            principal_id=None,
            key_id=parsed.key_id,
            outcome="error",
            request=request,
        )
        raise _internal_error() from error
    except sqlite3.Error as error:
        # A genuine DB failure during lookup — whether a row for this
        # key_id exists cannot be confirmed, so the attempted (client-
        # supplied, unverified) key_id is not recorded.
        _record_event_safely(
            audit, principal_id=None, key_id=None, outcome="error", request=request
        )
        raise _internal_error() from error

    if stored is None:
        _record_event_safely(
            audit, principal_id=None, key_id=None, outcome="rejected", request=request
        )
        raise _unauthorized()

    if not verify_api_key(parsed.secret, stored.verifier):
        _record_event_safely(
            audit,
            principal_id=None,
            key_id=stored.key_id,
            outcome="rejected",
            request=request,
        )
        raise _unauthorized()

    try:
        principal = repository.get_principal(stored.principal_id)
    except (ValueError, sqlite3.Error) as error:
        _record_event_safely(
            audit,
            principal_id=None,
            key_id=stored.key_id,
            outcome="error",
            request=request,
        )
        raise _internal_error() from error

    if principal is None:
        _record_event_safely(
            audit,
            principal_id=None,
            key_id=stored.key_id,
            outcome="error",
            request=request,
        )
        raise _internal_error()

    _record_event_safely(
        audit,
        principal_id=principal.principal_id,
        key_id=stored.key_id,
        outcome="success",
        request=request,
    )
    return principal
