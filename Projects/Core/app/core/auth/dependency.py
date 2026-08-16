import sqlite3
from pathlib import Path

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth.credentials import parse_api_key, verify_api_key
from app.core.auth.principal import Principal
from app.core.auth.repository import SqliteAuthRepository


_bearer_scheme = HTTPBearer(auto_error=True)


def get_auth_repository() -> SqliteAuthRepository:
    database_path = (
        Path(__file__).resolve().parents[5] / "Databases" / "core_auth.db"
    )
    return SqliteAuthRepository(database_path)


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


def require_principal(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    repository: SqliteAuthRepository = Depends(get_auth_repository),
) -> Principal:
    try:
        parsed = parse_api_key(credentials.credentials)
    except ValueError as error:
        raise _unauthorized() from error

    try:
        stored = repository.find_credential_by_key_id(parsed.key_id)
    except (ValueError, sqlite3.Error) as error:
        raise _internal_error() from error

    if stored is None:
        raise _unauthorized()

    if not verify_api_key(parsed.secret, stored.verifier):
        raise _unauthorized()

    try:
        principal = repository.get_principal(stored.principal_id)
    except (ValueError, sqlite3.Error) as error:
        raise _internal_error() from error

    if principal is None:
        raise _internal_error()

    return principal
