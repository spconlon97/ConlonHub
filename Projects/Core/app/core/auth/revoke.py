import argparse
import json
import sys
from pathlib import Path

from app.core.auth.bootstrap import default_database_path
from app.core.auth.credentials import is_valid_key_id
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
    parser = build_parser()
    tokens = list(sys.argv[1:] if argv is None else argv)
    # URL-safe IDs may start with '-', which argparse treats as an option.
    # Bind an ID to its flag without consuming actual supported CLI options.
    options = {option for action in parser._actions for option in action.option_strings}
    for index in range(len(tokens) - 1):
        if (
            tokens[index] == "--key-id"
            and tokens[index + 1] not in options
            and is_valid_key_id(tokens[index + 1])
        ):
            tokens[index:index + 2] = [f"--key-id={tokens[index + 1]}"]
            break
    arguments = parser.parse_args(tokens)
    repository = SqliteAuthRepository(arguments.database)

    if arguments.list:
        print(json.dumps({"api_keys": repository.list_api_keys()}))
        return 0

    revoked = repository.revoke_api_key(arguments.key_id)
    print(json.dumps({"key_id": arguments.key_id, "revoked": revoked}))
    return 0 if revoked else 1


if __name__ == "__main__":
    raise SystemExit(main())
