import argparse
import json
import uuid
from pathlib import Path

from app.core.auth.credentials import generate_api_key, hash_api_key
from app.core.auth.principal import Principal
from app.core.auth.repository import SqliteAuthRepository


def default_database_path() -> Path:
    return Path(__file__).resolve().parents[5] / "Databases" / "core_auth.db"


def bootstrap_principal(database_path, *, name: str, principal_id: str | None = None):
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must be a non-empty string.")
    if principal_id is None:
        principal_id = str(uuid.uuid4())

    principal = Principal(principal_id=principal_id, name=name.strip())
    issued = generate_api_key()
    verifier = hash_api_key(issued.secret)
    repository = SqliteAuthRepository(database_path)
    repository.create_principal_with_api_key(
        principal, issued.key_id, verifier
    )
    return principal, issued


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a local Conlon Hub principal and one API key."
    )
    parser.add_argument("--name", required=True, help="Display name for the principal.")
    parser.add_argument(
        "--principal-id",
        help="Stable principal ID. A UUID is generated when omitted.",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=default_database_path(),
        help="Authentication SQLite path.",
    )
    return parser


def main(argv=None) -> int:
    arguments = build_parser().parse_args(argv)
    principal, issued = bootstrap_principal(
        arguments.database,
        name=arguments.name,
        principal_id=arguments.principal_id,
    )
    print(
        json.dumps(
            {
                "principal_id": principal.principal_id,
                "name": principal.name,
                "api_key": issued.token,
                "warning": "Store api_key securely; it cannot be recovered.",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
