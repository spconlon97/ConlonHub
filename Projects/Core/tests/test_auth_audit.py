import sqlite3
import unittest
import uuid
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.core.auth.audit import AuditEvent, SqliteAuditRepository


class SqliteAuditRepositoryTests(unittest.TestCase):
    def _database_path(self, temp_dir):
        return Path(temp_dir) / "audit.db"

    def test_records_and_persists_an_event(self):
        with TemporaryDirectory() as temp_dir:
            database_path = self._database_path(temp_dir)
            repository = SqliteAuditRepository(database_path)

            event = repository.record_event(
                principal_id="p-1",
                key_id="key-1",
                event_type="auth.whoami",
                outcome="success",
                method="GET",
                path="/auth/whoami",
            )

            with closing(sqlite3.connect(database_path)) as connection:
                rows = connection.execute(
                    """
                    SELECT event_id, occurred_at, principal_id, key_id,
                           event_type, outcome, method, path
                    FROM audit_events
                    WHERE event_id = ?
                    """,
                    (event.event_id,),
                ).fetchall()

            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row[0], event.event_id)
            self.assertEqual(row[1], event.occurred_at)
            self.assertEqual(row[2], "p-1")
            self.assertEqual(row[3], "key-1")
            self.assertEqual(row[4], "auth.whoami")
            self.assertEqual(row[5], "success")
            self.assertEqual(row[6], "GET")
            self.assertEqual(row[7], "/auth/whoami")

    def test_generated_event_id_is_a_valid_uuid4(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAuditRepository(self._database_path(temp_dir))

            event = repository.record_event(
                principal_id=None,
                key_id=None,
                event_type="auth.whoami",
                outcome="rejected",
                method="GET",
                path="/auth/whoami",
            )

            parsed = uuid.UUID(event.event_id)
            self.assertEqual(parsed.version, 4)

    def test_separate_calls_produce_deterministically_distinct_event_ids(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAuditRepository(self._database_path(temp_dir))
            fixed_ids = [uuid.UUID(int=1), uuid.UUID(int=2)]

            with patch("app.core.auth.audit.uuid.uuid4", side_effect=fixed_ids):
                first = repository.record_event(
                    principal_id=None,
                    key_id=None,
                    event_type="auth.whoami",
                    outcome="rejected",
                    method="GET",
                    path="/auth/whoami",
                )
                second = repository.record_event(
                    principal_id=None,
                    key_id=None,
                    event_type="auth.whoami",
                    outcome="rejected",
                    method="GET",
                    path="/auth/whoami",
                )

            self.assertEqual(first.event_id, str(fixed_ids[0]))
            self.assertEqual(second.event_id, str(fixed_ids[1]))
            self.assertNotEqual(first.event_id, second.event_id)

    def test_occurred_at_is_utc_iso8601_timezone_aware(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAuditRepository(self._database_path(temp_dir))

            event = repository.record_event(
                principal_id=None,
                key_id=None,
                event_type="auth.whoami",
                outcome="success",
                method="GET",
                path="/auth/whoami",
            )

            parsed = datetime.fromisoformat(event.occurred_at)
            self.assertIsNotNone(parsed.tzinfo)
            self.assertEqual(parsed.utcoffset(), timedelta(0))

    def test_principal_id_and_key_id_may_be_null(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAuditRepository(self._database_path(temp_dir))

            event = repository.record_event(
                principal_id=None,
                key_id=None,
                event_type="auth.whoami",
                outcome="rejected",
                method="GET",
                path="/auth/whoami",
            )

            self.assertIsNone(event.principal_id)
            self.assertIsNone(event.key_id)

    def test_rejects_invalid_outcome(self):
        with self.assertRaisesRegex(ValueError, "outcome must be one of"):
            AuditEvent(
                event_id=str(uuid.uuid4()),
                occurred_at="2026-01-01T00:00:00+00:00",
                principal_id=None,
                key_id=None,
                event_type="auth.whoami",
                outcome="maybe",
                method="GET",
                path="/auth/whoami",
            )

    def test_rejects_empty_required_fields(self):
        with self.assertRaisesRegex(ValueError, "method must be"):
            AuditEvent(
                event_id=str(uuid.uuid4()),
                occurred_at="2026-01-01T00:00:00+00:00",
                principal_id=None,
                key_id=None,
                event_type="auth.whoami",
                outcome="success",
                method="",
                path="/auth/whoami",
            )

    def test_no_field_can_hold_secret_or_token_like_values(self):
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            occurred_at="2026-01-01T00:00:00+00:00",
            principal_id="p-1",
            key_id="key-1",
            event_type="auth.whoami",
            outcome="success",
            method="GET",
            path="/auth/whoami",
        )
        for forbidden in ("secret", "token", "salt", "digest", "password"):
            self.assertFalse(hasattr(event, forbidden))

    def test_rejects_non_uuid_event_id(self):
        with self.assertRaisesRegex(ValueError, "valid UUID"):
            AuditEvent(
                event_id="not-a-uuid",
                occurred_at="2026-01-01T00:00:00+00:00",
                principal_id=None,
                key_id=None,
                event_type="auth.whoami",
                outcome="success",
                method="GET",
                path="/auth/whoami",
            )

    def test_rejects_malformed_occurred_at(self):
        with self.assertRaisesRegex(ValueError, "valid ISO-8601"):
            AuditEvent(
                event_id=str(uuid.uuid4()),
                occurred_at="not-a-timestamp",
                principal_id=None,
                key_id=None,
                event_type="auth.whoami",
                outcome="success",
                method="GET",
                path="/auth/whoami",
            )

    def test_rejects_naive_occurred_at(self):
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            AuditEvent(
                event_id=str(uuid.uuid4()),
                occurred_at="2026-01-01T00:00:00",
                principal_id=None,
                key_id=None,
                event_type="auth.whoami",
                outcome="success",
                method="GET",
                path="/auth/whoami",
            )

    def test_rejects_non_utc_occurred_at(self):
        with self.assertRaisesRegex(ValueError, "must be in UTC"):
            AuditEvent(
                event_id=str(uuid.uuid4()),
                occurred_at="2026-01-01T00:00:00+05:00",
                principal_id=None,
                key_id=None,
                event_type="auth.whoami",
                outcome="success",
                method="GET",
                path="/auth/whoami",
            )


if __name__ == "__main__":
    unittest.main()
