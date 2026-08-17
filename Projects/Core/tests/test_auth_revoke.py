import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from app.core.auth.credentials import generate_api_key, hash_api_key
from app.core.auth.principal import Principal
from app.core.auth.repository import SqliteAuthRepository
from app.core.auth.revoke import main


class AuthRevocationTests(unittest.TestCase):
    def _repository_with_key(self, database_path):
        repository = SqliteAuthRepository(database_path)
        issued = generate_api_key()
        repository.create_principal_with_api_key(
            Principal("owner", "Owner"),
            issued.key_id,
            hash_api_key(issued.secret),
        )
        return repository, issued

    def test_lists_only_non_secret_key_metadata(self):
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "auth.db"
            _repository, issued = self._repository_with_key(database_path)

            keys = SqliteAuthRepository(database_path).list_api_keys()

            self.assertEqual(len(keys), 1)
            self.assertEqual(keys[0]["key_id"], issued.key_id)
            self.assertEqual(keys[0]["principal_id"], "owner")
            self.assertTrue(keys[0]["created_at"])
            self.assertNotIn(issued.secret, repr(keys))
            self.assertNotIn(issued.token, repr(keys))

    def test_revoked_key_can_no_longer_be_found(self):
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "auth.db"
            repository, issued = self._repository_with_key(database_path)

            self.assertTrue(repository.revoke_api_key(issued.key_id))

            self.assertIsNone(repository.find_credential_by_key_id(issued.key_id))
            self.assertIsNotNone(repository.get_principal("owner"))
            self.assertFalse(repository.revoke_api_key(issued.key_id))

    def test_command_lists_and_revokes_key(self):
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "auth.db"
            _repository, issued = self._repository_with_key(database_path)

            list_output = io.StringIO()
            with redirect_stdout(list_output):
                list_exit = main(["--list", "--database", str(database_path)])

            listed = json.loads(list_output.getvalue())
            self.assertEqual(list_exit, 0)
            self.assertEqual(listed["api_keys"][0]["key_id"], issued.key_id)

            revoke_output = io.StringIO()
            with redirect_stdout(revoke_output):
                revoke_exit = main(
                    [
                        "--key-id",
                        issued.key_id,
                        "--database",
                        str(database_path),
                    ]
                )

            self.assertEqual(revoke_exit, 0)
            self.assertEqual(
                json.loads(revoke_output.getvalue()),
                {"key_id": issued.key_id, "revoked": True},
            )


if __name__ == "__main__":
    unittest.main()
