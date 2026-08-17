import sqlite3
import unittest
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from app.core.auth import (
    Principal,
    StoredCredential,
    SqliteAuthRepository,
    generate_api_key,
    hash_api_key,
    verify_api_key,
)


class SqliteAuthRepositoryTests(unittest.TestCase):
    def _database_path(self, temp_dir):
        return Path(temp_dir) / "auth.db"

    def _assert_value_not_persisted_anywhere(self, database_path, value: str):
        encoded = value.encode("utf-8")

        with closing(sqlite3.connect(database_path)) as connection:
            for table_name in ("principals", "api_keys"):
                rows = connection.execute(f"SELECT * FROM {table_name}").fetchall()
                for row in rows:
                    for column_value in row:
                        if isinstance(column_value, (bytes, bytearray)):
                            self.assertNotIn(encoded, bytes(column_value))
                        elif isinstance(column_value, str):
                            self.assertNotIn(value, column_value)

        raw_bytes = database_path.read_bytes()
        self.assertNotIn(encoded, raw_bytes)

    def test_creates_and_retrieves_a_principal(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAuthRepository(self._database_path(temp_dir))
            principal = Principal(principal_id="p-1", name="Test Principal")

            repository.create_principal(principal)
            retrieved = repository.get_principal("p-1")

            self.assertEqual(retrieved, principal)

    def test_get_principal_returns_none_for_unknown_id(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAuthRepository(self._database_path(temp_dir))

            self.assertIsNone(repository.get_principal("does-not-exist"))

    def test_rejects_duplicate_principal_id(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAuthRepository(self._database_path(temp_dir))
            repository.create_principal(Principal(principal_id="p-1", name="First"))

            with self.assertRaisesRegex(ValueError, "p-1"):
                repository.create_principal(
                    Principal(principal_id="p-1", name="Second")
                )

    def test_verifier_round_trips_and_verifies_correctly(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAuthRepository(self._database_path(temp_dir))
            repository.create_principal(Principal(principal_id="p-1", name="Test"))

            verifier = hash_api_key("correct-horse-battery-staple", salt=b"\x00" * 16)
            repository.add_api_key_verifier("key-1", "p-1", verifier)

            stored = repository.find_credential_by_key_id("key-1")

            self.assertTrue(
                verify_api_key("correct-horse-battery-staple", stored.verifier)
            )

    def test_finds_credential_by_key_id(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAuthRepository(self._database_path(temp_dir))
            repository.create_principal(Principal(principal_id="p-1", name="Test"))

            verifier = hash_api_key("another-secret-value", salt=b"\x01" * 16)
            repository.add_api_key_verifier("key-1", "p-1", verifier)

            stored = repository.find_credential_by_key_id("key-1")

            self.assertIsInstance(stored, StoredCredential)
            self.assertEqual(stored.key_id, "key-1")
            self.assertEqual(stored.principal_id, "p-1")
            self.assertEqual(stored.verifier.scheme, verifier.scheme)
            self.assertEqual(stored.verifier.salt, verifier.salt)
            self.assertEqual(stored.verifier.digest, verifier.digest)

    def test_find_credential_returns_none_for_unknown_key_id(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAuthRepository(self._database_path(temp_dir))

            self.assertIsNone(repository.find_credential_by_key_id("does-not-exist"))

    def test_rejects_duplicate_key_id(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAuthRepository(self._database_path(temp_dir))
            repository.create_principal(Principal(principal_id="p-1", name="Test"))

            verifier = hash_api_key("secret-one", salt=b"\x02" * 16)
            repository.add_api_key_verifier("key-1", "p-1", verifier)

            other_verifier = hash_api_key("secret-two", salt=b"\x03" * 16)
            with self.assertRaisesRegex(ValueError, "key-1"):
                repository.add_api_key_verifier("key-1", "p-1", other_verifier)

    def test_rejects_api_key_for_unknown_principal(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAuthRepository(self._database_path(temp_dir))

            verifier = hash_api_key("orphan-secret", salt=b"\x04" * 16)

            with self.assertRaisesRegex(ValueError, "does-not-exist"):
                repository.add_api_key_verifier("key-1", "does-not-exist", verifier)

    def test_foreign_key_pragma_is_enabled_on_repository_connections(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAuthRepository(self._database_path(temp_dir))

            with closing(repository._connect()) as connection:
                status = connection.execute("PRAGMA foreign_keys").fetchone()[0]

            self.assertEqual(status, 1)

    def test_malformed_stored_scheme_fails_safely_on_reconstruction(self):
        with TemporaryDirectory() as temp_dir:
            database_path = self._database_path(temp_dir)
            repository = SqliteAuthRepository(database_path)
            repository.create_principal(Principal(principal_id="p-1", name="Test"))
            verifier = hash_api_key("some-secret", salt=b"\x05" * 16)
            repository.add_api_key_verifier("key-1", "p-1", verifier)

            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute(
                    "UPDATE api_keys SET scheme = ? WHERE key_id = ?",
                    ("unsupported-scheme-v0", "key-1"),
                )
                connection.commit()

            with self.assertRaises(ValueError):
                repository.find_credential_by_key_id("key-1")

    def test_malformed_stored_salt_fails_safely_on_reconstruction(self):
        with TemporaryDirectory() as temp_dir:
            database_path = self._database_path(temp_dir)
            repository = SqliteAuthRepository(database_path)
            repository.create_principal(Principal(principal_id="p-1", name="Test"))
            verifier = hash_api_key("some-secret", salt=b"\x05" * 16)
            repository.add_api_key_verifier("key-1", "p-1", verifier)

            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute(
                    "UPDATE api_keys SET salt = ? WHERE key_id = ?",
                    (b"\x00" * 4, "key-1"),
                )
                connection.commit()

            with self.assertRaises(ValueError):
                repository.find_credential_by_key_id("key-1")

    def test_malformed_stored_digest_fails_safely_on_reconstruction(self):
        with TemporaryDirectory() as temp_dir:
            database_path = self._database_path(temp_dir)
            repository = SqliteAuthRepository(database_path)
            repository.create_principal(Principal(principal_id="p-1", name="Test"))
            verifier = hash_api_key("some-secret", salt=b"\x05" * 16)
            repository.add_api_key_verifier("key-1", "p-1", verifier)

            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute(
                    "UPDATE api_keys SET digest = ? WHERE key_id = ?",
                    (b"\x00" * 10, "key-1"),
                )
                connection.commit()

            with self.assertRaises(ValueError):
                repository.find_credential_by_key_id("key-1")

    def test_reopening_repository_preserves_principal_and_credential(self):
        with TemporaryDirectory() as temp_dir:
            database_path = self._database_path(temp_dir)
            repository = SqliteAuthRepository(database_path)
            principal = Principal(principal_id="p-1", name="Test Principal")
            repository.create_principal(principal)
            verifier = hash_api_key("persisted-secret", salt=b"\x06" * 16)
            repository.add_api_key_verifier("key-1", "p-1", verifier)

            reopened = SqliteAuthRepository(database_path)

            self.assertEqual(reopened.get_principal("p-1"), principal)
            stored = reopened.find_credential_by_key_id("key-1")
            self.assertEqual(stored.principal_id, "p-1")
            self.assertEqual(stored.verifier.digest, verifier.digest)

    def test_plaintext_secret_is_never_persisted(self):
        with TemporaryDirectory() as temp_dir:
            database_path = self._database_path(temp_dir)
            repository = SqliteAuthRepository(database_path)
            repository.create_principal(Principal(principal_id="p-1", name="Test"))

            distinctive_secret = "UNMISTAKABLE-PLAINTEXT-SECRET-MARKER-7f3e9c1a"
            verifier = hash_api_key(distinctive_secret, salt=b"\x07" * 16)
            repository.add_api_key_verifier("key-1", "p-1", verifier)

            self._assert_value_not_persisted_anywhere(database_path, distinctive_secret)

    def test_full_issued_token_is_never_persisted(self):
        with TemporaryDirectory() as temp_dir:
            database_path = self._database_path(temp_dir)
            repository = SqliteAuthRepository(database_path)
            repository.create_principal(Principal(principal_id="p-1", name="Test"))

            issued = generate_api_key()
            verifier = hash_api_key(issued.secret, salt=b"\x08" * 16)
            repository.add_api_key_verifier(issued.key_id, "p-1", verifier)

            self._assert_value_not_persisted_anywhere(database_path, issued.token)

    def test_error_messages_do_not_contain_verifier_material(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAuthRepository(self._database_path(temp_dir))
            repository.create_principal(Principal(principal_id="p-1", name="Test"))

            verifier = hash_api_key("some-secret-value", salt=b"\x09" * 16)
            repository.add_api_key_verifier("key-1", "p-1", verifier)

            with self.assertRaises(ValueError) as raised:
                repository.add_api_key_verifier("key-1", "p-1", verifier)

            message = str(raised.exception)
            self.assertNotIn(verifier.salt.hex(), message)
            self.assertNotIn(verifier.digest.hex(), message)
            self.assertNotIn(repr(verifier.salt), message)
            self.assertNotIn(repr(verifier.digest), message)

    def test_principal_created_at_is_a_timezone_aware_utc_iso8601_timestamp(self):
        with TemporaryDirectory() as temp_dir:
            database_path = self._database_path(temp_dir)
            repository = SqliteAuthRepository(database_path)
            repository.create_principal(Principal(principal_id="p-1", name="Test"))

            with closing(sqlite3.connect(database_path)) as connection:
                row = connection.execute(
                    "SELECT created_at FROM principals WHERE principal_id = ?",
                    ("p-1",),
                ).fetchone()

            self.assertIsNotNone(row)
            created_at_raw = row[0]
            self.assertTrue(created_at_raw)

            parsed = datetime.fromisoformat(created_at_raw)

            self.assertIsNotNone(parsed.tzinfo)
            self.assertEqual(parsed.utcoffset(), timedelta(0))

    def test_api_key_created_at_is_a_timezone_aware_utc_iso8601_timestamp(self):
        with TemporaryDirectory() as temp_dir:
            database_path = self._database_path(temp_dir)
            repository = SqliteAuthRepository(database_path)
            repository.create_principal(Principal(principal_id="p-1", name="Test"))
            verifier = hash_api_key("some-secret", salt=b"\x0a" * 16)
            repository.add_api_key_verifier("key-1", "p-1", verifier)

            with closing(sqlite3.connect(database_path)) as connection:
                row = connection.execute(
                    "SELECT created_at FROM api_keys WHERE key_id = ?",
                    ("key-1",),
                ).fetchone()

            self.assertIsNotNone(row)
            created_at_raw = row[0]
            self.assertTrue(created_at_raw)

            parsed = datetime.fromisoformat(created_at_raw)

            self.assertIsNotNone(parsed.tzinfo)
            self.assertEqual(parsed.utcoffset(), timedelta(0))

    def test_rejects_empty_key_id(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAuthRepository(self._database_path(temp_dir))
            repository.create_principal(Principal(principal_id="p-1", name="Test"))

            verifier = hash_api_key("some-secret", salt=b"\x0b" * 16)

            with self.assertRaisesRegex(ValueError, "URL-safe"):
                repository.add_api_key_verifier("", "p-1", verifier)

    def test_rejects_malformed_key_id(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAuthRepository(self._database_path(temp_dir))
            repository.create_principal(Principal(principal_id="p-1", name="Test"))

            verifier = hash_api_key("some-secret", salt=b"\x0c" * 16)

            with self.assertRaisesRegex(ValueError, "URL-safe"):
                repository.add_api_key_verifier("contains.dot", "p-1", verifier)

            with self.assertRaisesRegex(ValueError, "URL-safe"):
                repository.add_api_key_verifier("bad key!", "p-1", verifier)

    def test_no_row_created_when_key_id_is_invalid(self):
        with TemporaryDirectory() as temp_dir:
            database_path = self._database_path(temp_dir)
            repository = SqliteAuthRepository(database_path)
            repository.create_principal(Principal(principal_id="p-1", name="Test"))

            verifier = hash_api_key("some-secret", salt=b"\x0d" * 16)

            with self.assertRaises(ValueError):
                repository.add_api_key_verifier("", "p-1", verifier)

            with self.assertRaises(ValueError):
                repository.add_api_key_verifier("bad key!", "p-1", verifier)

            with closing(sqlite3.connect(database_path)) as connection:
                count = connection.execute("SELECT COUNT(*) FROM api_keys").fetchone()[0]

            self.assertEqual(count, 0)

    def test_rejects_none_principal_id_when_adding_api_key(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAuthRepository(self._database_path(temp_dir))

            verifier = hash_api_key("some-secret", salt=b"\x0e" * 16)

            with self.assertRaisesRegex(ValueError, "principal_id"):
                repository.add_api_key_verifier("key-1", None, verifier)

    def test_rejects_blank_principal_id_when_adding_api_key(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAuthRepository(self._database_path(temp_dir))

            verifier = hash_api_key("some-secret", salt=b"\x0f" * 16)

            with self.assertRaisesRegex(ValueError, "principal_id"):
                repository.add_api_key_verifier("key-1", "   ", verifier)

    def test_no_row_created_for_invalid_principal_id(self):
        with TemporaryDirectory() as temp_dir:
            database_path = self._database_path(temp_dir)
            repository = SqliteAuthRepository(database_path)

            verifier = hash_api_key("some-secret", salt=b"\x10" * 16)

            with self.assertRaises(ValueError):
                repository.add_api_key_verifier("key-1", None, verifier)

            with self.assertRaises(ValueError):
                repository.add_api_key_verifier("key-2", "   ", verifier)

            with closing(sqlite3.connect(database_path)) as connection:
                count = connection.execute("SELECT COUNT(*) FROM api_keys").fetchone()[0]

            self.assertEqual(count, 0)

    def test_principal_and_key_creation_is_atomic(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAuthRepository(self._database_path(temp_dir))
            verifier = hash_api_key("some-secret", salt=b"\x11" * 16)
            repository.create_principal_with_api_key(
                Principal("p-1", "First"), "duplicate-key", verifier
            )

            with self.assertRaises(ValueError):
                repository.create_principal_with_api_key(
                    Principal("p-2", "Second"), "duplicate-key", verifier
                )

            self.assertIsNone(repository.get_principal("p-2"))


if __name__ == "__main__":
    unittest.main()
