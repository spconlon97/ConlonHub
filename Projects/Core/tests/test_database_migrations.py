import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from app.core.database import current_schema_version, migrate_database


class DatabaseMigrationTests(unittest.TestCase):
    def test_blank_database_is_migrated_to_latest_version(self):
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "blank.db"

            self.assertEqual(migrate_database(database_path, "auth"), 1)
            self.assertEqual(current_schema_version(database_path, "auth"), 1)

            with closing(sqlite3.connect(database_path)) as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }

            self.assertTrue(
                {
                    "schema_migrations",
                    "principals",
                    "api_keys",
                }.issubset(tables)
            )
            self.assertNotIn("audit_events", tables)
            self.assertNotIn("paper_orders", tables)

    def test_repeated_migration_is_idempotent(self):
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "repeated.db"

            migrate_database(database_path, "paper_orders")
            migrate_database(database_path, "paper_orders")

            with closing(sqlite3.connect(database_path)) as connection:
                rows = connection.execute(
                    """
                    SELECT component, version, name
                    FROM schema_migrations
                    ORDER BY component, version
                    """
                ).fetchall()

            self.assertEqual(
                rows,
                [
                    ("paper_orders", 1, "create_paper_orders_table"),
                ],
            )

    def test_legacy_database_is_adopted_without_data_loss(self):
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "legacy.db"
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute(
                    """
                    CREATE TABLE principals (
                        principal_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    "INSERT INTO principals VALUES ('legacy', 'Legacy User', 'then')"
                )
                connection.commit()

            self.assertEqual(current_schema_version(database_path, "auth"), 0)
            migrate_database(database_path, "auth")

            with closing(sqlite3.connect(database_path)) as connection:
                principal = connection.execute(
                    "SELECT principal_id, name FROM principals"
                ).fetchone()

            self.assertEqual(principal, ("legacy", "Legacy User"))
            self.assertEqual(current_schema_version(database_path, "auth"), 1)

    def test_legacy_migration_metadata_is_upgraded(self):
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "old_metadata.db"
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute(
                    """
                    CREATE TABLE schema_migrations (
                        version INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                connection.execute(
                    "INSERT INTO schema_migrations (version, name) VALUES (1, 'old')"
                )
                connection.commit()

            migrate_database(database_path, "audit")

            self.assertEqual(current_schema_version(database_path, "audit"), 1)
            with closing(sqlite3.connect(database_path)) as connection:
                columns = {
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(schema_migrations)"
                    )
                }
            self.assertIn("component", columns)


if __name__ == "__main__":
    unittest.main()
