import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.core.auth.credentials import ApiKeyVerifier, is_valid_key_id
from app.core.auth.principal import Principal


@dataclass(frozen=True)
class StoredCredential:
    key_id: str
    principal_id: str
    verifier: ApiKeyVerifier


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteAuthRepository:
    def __init__(self, database_path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self):
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS principals (
                    principal_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS api_keys (
                    key_id TEXT PRIMARY KEY,
                    principal_id TEXT NOT NULL,
                    scheme TEXT NOT NULL,
                    salt BLOB NOT NULL,
                    digest BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (principal_id) REFERENCES principals(principal_id)
                )
                """
            )
            connection.commit()

    def create_principal(self, principal: Principal) -> None:
        with closing(self._connect()) as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO principals (principal_id, name, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (principal.principal_id, principal.name, _utc_now_iso()),
                )
                connection.commit()
            except sqlite3.IntegrityError as error:
                raise ValueError(
                    f"principal_id {principal.principal_id!r} already exists."
                ) from error

    def get_principal(self, principal_id: str) -> Principal | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT principal_id, name
                FROM principals
                WHERE principal_id = ?
                """,
                (principal_id,),
            ).fetchone()

        if row is None:
            return None

        return Principal(principal_id=row[0], name=row[1])

    def add_api_key_verifier(
        self, key_id: str, principal_id: str, verifier: ApiKeyVerifier
    ) -> None:
        if not is_valid_key_id(key_id):
            raise ValueError("key_id must be a non-empty URL-safe string.")

        if not isinstance(principal_id, str) or not principal_id.strip():
            raise ValueError("principal_id must be a non-empty string.")

        with closing(self._connect()) as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO api_keys (
                        key_id, principal_id, scheme, salt, digest, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        key_id,
                        principal_id,
                        verifier.scheme,
                        verifier.salt,
                        verifier.digest,
                        _utc_now_iso(),
                    ),
                )
                connection.commit()
            except sqlite3.IntegrityError as error:
                message = str(error)
                if "FOREIGN KEY" in message:
                    raise ValueError(
                        f"principal_id {principal_id!r} does not exist."
                    ) from error
                raise ValueError(f"key_id {key_id!r} already exists.") from error

    def find_credential_by_key_id(self, key_id: str) -> StoredCredential | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT key_id, principal_id, scheme, salt, digest
                FROM api_keys
                WHERE key_id = ?
                """,
                (key_id,),
            ).fetchone()

        if row is None:
            return None

        stored_key_id, principal_id, scheme, salt, digest = row

        verifier = ApiKeyVerifier(scheme=scheme, salt=salt, digest=digest)

        return StoredCredential(
            key_id=stored_key_id,
            principal_id=principal_id,
            verifier=verifier,
        )
