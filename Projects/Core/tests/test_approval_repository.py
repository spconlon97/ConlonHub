import re
import sqlite3
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from app.core.approvals.models import ApprovalStatus, arguments_digest
from app.core.approvals.repository import (
    DEFAULT_APPROVAL_TTL,
    ApprovalNotFound,
    ApprovalNotPending,
    SqliteApprovalRepository,
)
from app.core.database import current_schema_version


_START = datetime(2026, 10, 23, 10, 0, tzinfo=timezone.utc)
_ARGUMENTS = {"symbol": "BTC-GBP", "side": "buy", "quantity": "0.01", "price": "50000"}


class FakeClock:
    def __init__(self, now=_START):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, delta):
        self.now += delta


class SqliteApprovalRepositoryTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = TemporaryDirectory()
        self.database_path = Path(self._temp_dir.name) / "approvals.db"
        self.clock = FakeClock()
        self.repository = SqliteApprovalRepository(self.database_path, clock=self.clock)

    def tearDown(self):
        self._temp_dir.cleanup()

    def _create(self, principal_id="p-1", **overrides):
        values = {
            "principal_id": principal_id,
            "capability": "trading.place_paper_order",
            "arguments": dict(_ARGUMENTS),
            "summary": "Buy 0.01 BTC-GBP at 50000 (paper)",
        }
        values.update(overrides)
        return self.repository.create(**values)

    # --- creation ----------------------------------------------------------

    def test_default_ttl_is_fifteen_minutes(self):
        self.assertEqual(DEFAULT_APPROVAL_TTL, timedelta(minutes=15))

    def test_created_request_is_pending_with_fifteen_minute_expiry(self):
        request = self._create()

        self.assertEqual(request.status, ApprovalStatus.PENDING)
        self.assertEqual(request.principal_id, "p-1")
        self.assertEqual(request.arguments, _ARGUMENTS)
        self.assertEqual(request.arguments_digest, arguments_digest(_ARGUMENTS))
        self.assertEqual(datetime.fromisoformat(request.created_at), _START)
        self.assertEqual(
            datetime.fromisoformat(request.expires_at), _START + timedelta(minutes=15)
        )
        self.assertIsNone(request.decided_at)

    def test_custom_ttl_must_be_positive(self):
        for ttl in (timedelta(0), timedelta(seconds=-1), 60):
            with self.subTest(ttl=ttl):
                with self.assertRaises(ValueError):
                    self._create(ttl=ttl)

    def test_invalid_input_is_rejected_and_not_stored(self):
        for overrides in (
            {"capability": ""},
            {"summary": "  "},
            {"arguments": {"x": object()}},
            {"principal_id": ""},
        ):
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValueError):
                    self._create(**overrides)

        with closing(sqlite3.connect(self.database_path)) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM approval_requests"
            ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_stored_arguments_are_a_copy(self):
        arguments = dict(_ARGUMENTS)
        request = self._create(arguments=arguments)
        arguments["quantity"] = "999"

        stored = self.repository.get(request.request_id, "p-1")
        self.assertEqual(stored.arguments["quantity"], "0.01")

    # --- reading -----------------------------------------------------------

    def test_get_returns_request_for_its_principal(self):
        request = self._create()

        self.assertEqual(self.repository.get(request.request_id, "p-1"), request)

    def test_other_principal_cannot_see_request(self):
        request = self._create()

        with self.assertRaises(ApprovalNotFound):
            self.repository.get(request.request_id, "p-2")

    def test_unknown_request_is_not_found(self):
        with self.assertRaises(ApprovalNotFound):
            self.repository.get("6f1c0a9e-2b1f-4a5e-9c0d-1a2b3c4d5e6f", "p-1")

    def test_list_pending_is_scoped_and_newest_first(self):
        first = self._create()
        self.clock.advance(timedelta(seconds=1))
        second = self._create()
        self._create(principal_id="p-2")

        pending = self.repository.list_pending("p-1")

        self.assertEqual(
            [item.request_id for item in pending],
            [second.request_id, first.request_id],
        )

    def test_list_pending_excludes_decided_and_expired(self):
        decided = self._create()
        self.repository.decide(decided.request_id, "p-1", approve=False)
        self._create()
        self.clock.advance(DEFAULT_APPROVAL_TTL)

        self.assertEqual(self.repository.list_pending("p-1"), ())

    def test_requests_survive_a_repository_restart(self):
        request = self._create()

        reopened = SqliteApprovalRepository(self.database_path, clock=self.clock)

        self.assertEqual(reopened.get(request.request_id, "p-1"), request)

    # --- deciding ----------------------------------------------------------

    def test_approve_once(self):
        request = self._create()
        self.clock.advance(timedelta(minutes=1))

        approved = self.repository.decide(request.request_id, "p-1", approve=True)

        self.assertEqual(approved.status, ApprovalStatus.APPROVED)
        self.assertEqual(
            datetime.fromisoformat(approved.decided_at), _START + timedelta(minutes=1)
        )
        self.assertEqual(approved.arguments_digest, request.arguments_digest)
        self.assertEqual(self.repository.get(request.request_id, "p-1"), approved)

    def test_reject_once(self):
        request = self._create()

        rejected = self.repository.decide(request.request_id, "p-1", approve=False)

        self.assertEqual(rejected.status, ApprovalStatus.REJECTED)

    def test_second_decision_is_refused_and_first_stands(self):
        for first, second in ((True, True), (True, False), (False, True)):
            with self.subTest(first=first, second=second):
                request = self._create()
                self.repository.decide(request.request_id, "p-1", approve=first)

                with self.assertRaises(ApprovalNotPending):
                    self.repository.decide(request.request_id, "p-1", approve=second)

                expected = ApprovalStatus.APPROVED if first else ApprovalStatus.REJECTED
                self.assertEqual(
                    self.repository.get(request.request_id, "p-1").status, expected
                )

    def test_decision_at_or_after_expiry_is_refused_and_marks_expired(self):
        request = self._create()
        self.clock.advance(DEFAULT_APPROVAL_TTL)

        with self.assertRaises(ApprovalNotPending):
            self.repository.decide(request.request_id, "p-1", approve=True)

        stored = self.repository.get(request.request_id, "p-1")
        self.assertEqual(stored.status, ApprovalStatus.EXPIRED)
        self.assertIsNone(stored.decided_at)

    def test_decision_just_before_expiry_succeeds(self):
        request = self._create()
        self.clock.advance(DEFAULT_APPROVAL_TTL - timedelta(microseconds=1))

        approved = self.repository.decide(request.request_id, "p-1", approve=True)

        self.assertEqual(approved.status, ApprovalStatus.APPROVED)

    def test_get_reports_stale_pending_request_as_expired(self):
        request = self._create()
        self.clock.advance(timedelta(hours=1))

        self.assertEqual(
            self.repository.get(request.request_id, "p-1").status,
            ApprovalStatus.EXPIRED,
        )

    def test_other_principal_cannot_decide(self):
        request = self._create()

        with self.assertRaises(ApprovalNotFound):
            self.repository.decide(request.request_id, "p-2", approve=True)

        self.assertEqual(
            self.repository.get(request.request_id, "p-1").status,
            ApprovalStatus.PENDING,
        )

    def test_decide_requires_a_boolean(self):
        request = self._create()

        for value in ("yes", 1, None):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    self.repository.decide(request.request_id, "p-1", approve=value)

    def test_concurrent_repositories_cannot_both_decide(self):
        request = self._create()
        other = SqliteApprovalRepository(self.database_path, clock=self.clock)

        self.repository.decide(request.request_id, "p-1", approve=True)

        with self.assertRaises(ApprovalNotPending):
            other.decide(request.request_id, "p-1", approve=False)

    # --- storage -----------------------------------------------------------

    def test_migration_is_recorded_and_repeatable(self):
        SqliteApprovalRepository(self.database_path, clock=self.clock)

        self.assertEqual(current_schema_version(self.database_path, "approvals"), 1)

    def test_database_rejects_unknown_status(self):
        with closing(sqlite3.connect(self.database_path)) as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO approval_requests (
                        request_id, principal_id, capability, arguments,
                        arguments_digest, summary, status, created_at, expires_at
                    ) VALUES ('id', 'p', 'c', '{}', 'd', 's', 'maybe', 't', 't')
                    """
                )

    def test_no_delete_operation_is_exposed(self):
        public = {name for name in dir(SqliteApprovalRepository) if not name.startswith("_")}

        self.assertEqual(public, {"create", "decide", "get", "list_pending"})


class ApprovalPackageIsolationTests(unittest.TestCase):
    def test_no_application_code_imports_approvals_yet(self):
        app_root = Path(__file__).resolve().parents[1] / "app"
        pattern = re.compile(r"^\s*(from|import)\s+app\.core\.approvals", re.MULTILINE)
        importers = [
            path.relative_to(app_root).as_posix()
            for path in app_root.rglob("*.py")
            if "approvals" not in path.parts and pattern.search(path.read_text(encoding="utf-8"))
        ]

        self.assertEqual(importers, [])


if __name__ == "__main__":
    unittest.main()
