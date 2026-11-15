import argparse
import json
from pathlib import Path

from app.core.auth.bootstrap import default_database_path
from app.core.auth.phone_devices import PAIRING_CODE_TTL, SqlitePhoneDeviceRepository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pair, list or revoke MARVIS phone browsers."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--new", action="store_true",
        help="Issue a one-time 6-digit pairing code (replaces any unused code).",
    )
    action.add_argument("--list", action="store_true", help="List paired phones.")
    action.add_argument("--revoke", metavar="DEVICE_ID", help="Revoke a paired phone.")
    parser.add_argument(
        "--database",
        type=Path,
        default=default_database_path(),
        help="Authentication SQLite path.",
    )
    return parser


def main(argv=None) -> int:
    arguments = build_parser().parse_args(argv)
    repository = SqlitePhoneDeviceRepository(arguments.database)

    if arguments.new:
        code = repository.create_pairing_code()
        minutes = int(PAIRING_CODE_TTL.total_seconds() // 60)
        print(json.dumps({"code": code, "expires_at": f"in {minutes} minutes"}))
        return 0

    if arguments.list:
        print(json.dumps({"devices": repository.list_devices()}))
        return 0

    revoked = repository.revoke(arguments.revoke)
    print(json.dumps({"device_id": arguments.revoke, "revoked": revoked}))
    return 0 if revoked else 1


if __name__ == "__main__":
    raise SystemExit(main())
