import hashlib
import hmac
import secrets
import string
from dataclasses import dataclass


_SEPARATOR = "."
_KEY_ID_BYTES = 12
_SECRET_BYTES = 32

# The salt provides per-credential diversification only — it is public and
# stored alongside the digest, never a server secret. It stops two identical
# secrets from hashing to the same digest and defeats precomputed tables, but
# it does NOT protect a fully leaked verifier table by itself. Offline brute
# force stays infeasible because generated secrets carry 256 bits of entropy,
# not because of the salt. A server-side pepper would add real protection
# against a full-table leak but needs a real secret lifecycle (env/secrets
# manager) that doesn't exist yet — deliberately not introduced here.
_SALT_BYTES = 16
_MIN_SALT_BYTES = 16

_HMAC_SHA256_V1 = "hmac-sha256-v1"
_SUPPORTED_SCHEMES = {_HMAC_SHA256_V1}
_EXPECTED_DIGEST_LENGTH = {_HMAC_SHA256_V1: hashlib.sha256().digest_size}

_URLSAFE_ALPHABET = frozenset(string.ascii_letters + string.digits + "-_")


def _is_urlsafe_token_component(value) -> bool:
    if not isinstance(value, str):
        return False

    return len(value) > 0 and all(char in _URLSAFE_ALPHABET for char in value)


def is_valid_key_id(value) -> bool:
    return _is_urlsafe_token_component(value)


@dataclass(frozen=True)
class IssuedApiKey:
    key_id: str
    secret: str
    token: str

    def __post_init__(self):
        if not is_valid_key_id(self.key_id):
            raise ValueError("key_id must be a non-empty URL-safe string.")

        if not _is_urlsafe_token_component(self.secret):
            raise ValueError("secret must be a non-empty URL-safe string.")

        expected_token = f"{self.key_id}{_SEPARATOR}{self.secret}"
        if self.token != expected_token:
            raise ValueError("token is inconsistent with key_id and secret.")

    def __repr__(self):
        return (
            f"IssuedApiKey(key_id={self.key_id!r}, "
            f"secret=<redacted>, token=<redacted>)"
        )


@dataclass(frozen=True)
class ParsedApiKey:
    key_id: str
    secret: str

    def __post_init__(self):
        if not is_valid_key_id(self.key_id):
            raise ValueError("key_id must be a non-empty URL-safe string.")

        if not _is_urlsafe_token_component(self.secret):
            raise ValueError("secret must be a non-empty URL-safe string.")

    def __repr__(self):
        return f"ParsedApiKey(key_id={self.key_id!r}, secret=<redacted>)"


@dataclass(frozen=True)
class ApiKeyVerifier:
    scheme: str
    salt: bytes
    digest: bytes

    def __post_init__(self):
        if not isinstance(self.scheme, str) or self.scheme not in _SUPPORTED_SCHEMES:
            raise ValueError(
                f"Unsupported or missing verifier scheme: {self.scheme!r}."
            )

        if not isinstance(self.salt, bytes):
            raise ValueError("salt must be bytes.")

        if len(self.salt) < _MIN_SALT_BYTES:
            raise ValueError(f"salt must be at least {_MIN_SALT_BYTES} bytes.")

        if not isinstance(self.digest, bytes):
            raise ValueError("digest must be bytes.")

        expected_length = _EXPECTED_DIGEST_LENGTH[self.scheme]
        if len(self.digest) != expected_length:
            raise ValueError(
                f"digest must be exactly {expected_length} bytes for scheme "
                f"{self.scheme!r}."
            )

    def __repr__(self):
        return (
            f"ApiKeyVerifier(scheme={self.scheme!r}, "
            f"salt=<{len(self.salt)} bytes redacted>, "
            f"digest=<{len(self.digest)} bytes redacted>)"
        )


def generate_api_key(
    *,
    key_id_bytes: int = _KEY_ID_BYTES,
    secret_bytes: int = _SECRET_BYTES,
) -> IssuedApiKey:
    if key_id_bytes < 6:
        raise ValueError("key_id_bytes must be at least 6.")

    if secret_bytes < 16:
        raise ValueError("secret_bytes must be at least 16 for a secure API key.")

    key_id = secrets.token_urlsafe(key_id_bytes)
    secret = secrets.token_urlsafe(secret_bytes)
    token = f"{key_id}{_SEPARATOR}{secret}"

    return IssuedApiKey(key_id=key_id, secret=secret, token=token)


def parse_api_key(token: str) -> ParsedApiKey:
    if not isinstance(token, str) or not token.strip():
        raise ValueError("token must be a non-empty string.")

    parts = token.split(_SEPARATOR)
    if len(parts) != 2:
        raise ValueError('token is malformed: expected exactly one "." separator.')

    return ParsedApiKey(key_id=parts[0], secret=parts[1])


def hash_api_key(secret: str, *, salt: bytes | None = None) -> ApiKeyVerifier:
    if not isinstance(secret, str) or not secret.strip():
        raise ValueError("secret must be a non-empty string.")

    if salt is not None and not isinstance(salt, bytes):
        raise ValueError("salt must be bytes.")

    resolved_salt = salt if salt is not None else secrets.token_bytes(_SALT_BYTES)

    digest = hmac.new(
        resolved_salt,
        secret.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    return ApiKeyVerifier(scheme=_HMAC_SHA256_V1, salt=resolved_salt, digest=digest)


def verify_api_key(secret: str, verifier: ApiKeyVerifier) -> bool:
    if not isinstance(secret, str) or not secret:
        return False

    if verifier.scheme not in _SUPPORTED_SCHEMES:
        return False

    if verifier.scheme == _HMAC_SHA256_V1:
        candidate = hmac.new(
            verifier.salt,
            secret.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return hmac.compare_digest(candidate, verifier.digest)

    return False
