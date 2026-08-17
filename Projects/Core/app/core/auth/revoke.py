import argparse
import json
from pathlib import Path

from app.core.auth.bootstrap import default_database_path
from app.core.auth.repository import SqliteAuthRepository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="List or revoke local Conlon Hub API credentials."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--list", action="store_true", help="List stored non-secret key metadata."
    )
    action.add_argument("--key-id", help="Revoke this exact API key ID.")
    parser.add_argument(
        "--database",
        type=Path,
        default=default_database_path(),
        help="Authentication SQLite path.",
    )
    return parser


def main(argv=None) -> int:
    arguments = build_parser().parse_args(argv)
    repository = SqliteAuthRepository(arguments.database)

    if arguments.list:
        print(json.dumps({"api_keys": repository.list_api_keys()}))
        return 0

    revoked = repository.revoke_api_key(arguments.key_id)
    print(json.dumps({"key_id": arguments.key_id, "revoked": revoked}))
    return 0 if revoked else 1


if __name__ == "__main__":
    raise SystemExit(main())
