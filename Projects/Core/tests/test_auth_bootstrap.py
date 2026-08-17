import io
import json
import sqlite3
import unittest
from contextlib import closing, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from app.core.auth.bootstrap import bootstrap_principal, main
from app.core.auth.credentials import parse_api_key, verify_api_key
from app.core.auth.repository import SqliteAuthRepository


class AuthBootstrapTests(unittest.TestCase):
    def test_creates_principal_and_usable_credential(self):
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "auth.db"

            principal, issued = bootstrap_principal(
                database_path, name="MARVIS Owner", principal_id="owner"
            )

            repository = SqliteAuthRepository(database_path)
            parsed = parse_api_key(issued.token)
            stored = repository.find_credential_by_key_id(parsed.key_id)
            self.assertEqual(repository.get_principal("owner"), principal)
            self.assertEqual(stored.principal_id, "owner")
            self.assertTrue(verify_api_key(parsed.secret, stored.verifier))

    def test_plaintext_token_is_not_stored(self):
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "auth.db"
            _principal, issued = bootstrap_principal(
                database_path, name="Owner"
            )

            with closing(sqlite3.connect(database_path)) as connection:
                dump = " ".join(
                    str(value)
                    for row in connection.execute("SELECT * FROM api_keys")
                    for value in row
                )

            self.assertNotIn(issued.token, dump)
            self.assertNotIn(issued.secret, dump)

    def test_command_prints_token_once_as_json(self):
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "auth.db"
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    [
                        "--name",
                        "Owner",
                        "--principal-id",
                        "owner",
                        "--database",
                        str(database_path),
                    ]
                )

            payload = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["principal_id"], "owner")
            self.assertEqual(payload["name"], "Owner")
            self.assertEqual(output.getvalue().count(payload["api_key"]), 1)
            self.assertIn("cannot be recovered", payload["warning"])

    def test_rejects_blank_name_without_creating_database(self):
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "auth.db"

            with self.assertRaisesRegex(ValueError, "name"):
                bootstrap_principal(database_path, name="   ")

            self.assertFalse(database_path.exists())


if __name__ == "__main__":
    unittest.main()
