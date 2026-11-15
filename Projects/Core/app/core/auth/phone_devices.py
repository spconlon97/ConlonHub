import hashlib
import hmac
import secrets
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.database import migrate_database


PAIRING_CODE_TTL = timedelta(minutes=5)
MAX_PAIRING_ATTEMPTS = 5
MAX_DEVICE_NAME_LENGTH = 60
_MAX_TOKEN_LENGTH = 200


class PairingFailed(ValueError):
    pass


@dataclass(frozen=True)
class PhoneDevice:
    device_id: str
    principal_id: str
    name: str
    created_at: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _clean_name(name) -> str:
    if not isinstance(name, str):
        return "Phone"
    return name.strip()[:MAX_DEVICE_NAME_LENGTH].strip() or "Phone"


class SqlitePhoneDeviceRepository:
    """Paired phone browsers. Only SHA-256 digests of codes and tokens are stored."""

    def __init__(self, database_path, clock=_utc_now):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        migrate_database(self.database_path, "phone_devices")

    def _connect(self):
        return sqlite3.connect(self.database_path)

    def create_pairing_code(self) -> str:
        code = f"{secrets.randbelow(1_000_000):06d}"
        now = self._clock()

        with closing(self._connect()) as connection:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                # Only one code is ever live: issuing a new one retires the old.
                connection.execute(
                    "UPDATE phone_pairing_codes SET used_at = ? WHERE used_at IS NULL",
                    (_timestamp(now),),
                )
                connection.execute(
                    "INSERT INTO phone_pairing_codes "
                    "(code_id, code_digest, created_at, expires_at, failed_attempts) "
                    "VALUES (?, ?, ?, ?, 0)",
                    (str(uuid.uuid4()), _digest(code), _timestamp(now),
                     _timestamp(now + PAIRING_CODE_TTL)),
                )

        return code

    def redeem(self, code, principal_id: str, device_name) -> tuple[PhoneDevice, str]:
        if not isinstance(principal_id, str) or not principal_id.strip():
            raise ValueError("principal_id must be a non-empty string.")

        now = _timestamp(self._clock())
        valid_format = isinstance(code, str) and len(code) == 6 and code.isdigit()

        with closing(self._connect()) as connection:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                active = connection.execute(
                    "SELECT code_id, code_digest, failed_attempts FROM phone_pairing_codes "
                    "WHERE used_at IS NULL AND expires_at > ? "
                    "ORDER BY created_at DESC LIMIT 1",
                    (now,),
                ).fetchone()
                if active is None:
                    raise PairingFailed("No active pairing code.")

                code_id, code_digest, failed = active
                if not valid_format or not hmac.compare_digest(_digest(code), code_digest):
                    failed += 1
                    # Burn the code after too many wrong guesses.
                    connection.execute(
                        "UPDATE phone_pairing_codes SET failed_attempts = ?, used_at = ? "
                        "WHERE code_id = ?",
                        (failed, now if failed >= MAX_PAIRING_ATTEMPTS else None, code_id),
                    )
                    result = None
                else:
                    token = secrets.token_urlsafe(32)
                    device = PhoneDevice(
                        device_id=str(uuid.uuid4()),
                        principal_id=principal_id,
                        name=_clean_name(device_name),
                        created_at=now,
                    )
                    connection.execute(
                        "UPDATE phone_pairing_codes SET used_at = ? WHERE code_id = ?",
                        (now, code_id),
                    )
                    connection.execute(
                        "INSERT INTO phone_devices "
                        "(device_id, principal_id, name, token_digest, created_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (device.device_id, device.principal_id, device.name,
                         _digest(token), device.created_at),
                    )
                    result = (device, token)

        # Raise after commit so the failed-attempt count is persisted.
        if result is None:
            raise PairingFailed("Pairing code is invalid.")
        return result

    def verify(self, token, principal_id: str) -> PhoneDevice | None:
        if not isinstance(token, str) or not token or len(token) > _MAX_TOKEN_LENGTH:
            return None

        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT device_id, principal_id, name, created_at FROM phone_devices "
                "WHERE token_digest = ? AND principal_id = ? AND revoked_at IS NULL",
                (_digest(token), principal_id),
            ).fetchone()

        return PhoneDevice(*row) if row else None

    def list_devices(self) -> list[dict]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT device_id, name, created_at, revoked_at FROM phone_devices "
                "ORDER BY created_at"
            ).fetchall()

        return [
            {"device_id": r[0], "name": r[1], "created_at": r[2], "revoked_at": r[3]}
            for r in rows
        ]

    def revoke(self, device_id: str) -> bool:
        with closing(self._connect()) as connection:
            with connection:
                updated = connection.execute(
                    "UPDATE phone_devices SET revoked_at = ? "
                    "WHERE device_id = ? AND revoked_at IS NULL",
                    (_timestamp(self._clock()), device_id),
                ).rowcount
        return updated == 1
