import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from app.core.approvals.models import (
    ApprovalRequest,
    ApprovalStatus,
    arguments_digest,
    canonical_arguments,
)


_CREATED = datetime(2026, 10, 23, 10, 0, tzinfo=timezone.utc)


def _request(**overrides):
    arguments = overrides.pop(
        "arguments", {"symbol": "BTC-GBP", "side": "buy", "quantity": "0.01"}
    )
    values = {
        "request_id": str(uuid.uuid4()),
        "principal_id": "p-1",
        "capability": "trading.place_paper_order",
        "arguments": arguments,
        "arguments_digest": arguments_digest(arguments),
        "summary": "Buy 0.01 BTC-GBP (paper)",
        "status": ApprovalStatus.PENDING,
        "created_at": _CREATED.isoformat(timespec="microseconds"),
        "expires_at": (_CREATED + timedelta(minutes=15)).isoformat(
            timespec="microseconds"
        ),
        "decided_at": None,
    }
    values.update(overrides)
    return ApprovalRequest(**values)


class ArgumentDigestTests(unittest.TestCase):
    def test_digest_ignores_key_order(self):
        self.assertEqual(
            arguments_digest({"a": 1, "b": "x"}),
            arguments_digest({"b": "x", "a": 1}),
        )

    def test_digest_changes_when_any_value_changes(self):
        self.assertNotEqual(
            arguments_digest({"quantity": "0.01"}),
            arguments_digest({"quantity": "0.02"}),
        )

    def test_digest_is_sha256_hex(self):
        digest = arguments_digest({})
        self.assertEqual(len(digest), 64)
        int(digest, 16)

    def test_canonical_form_is_compact_and_sorted(self):
        self.assertEqual(canonical_arguments({"b": 2, "a": 1}), '{"a":1,"b":2}')

    def test_non_object_arguments_are_rejected(self):
        for value in ([], "x", None, 1):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    canonical_arguments(value)

    def test_non_json_arguments_are_rejected(self):
        for value in ({"x": object()}, {"x": float("nan")}, {1: "non-string key"}):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    canonical_arguments(value)


class ApprovalRequestTests(unittest.TestCase):
    def test_valid_pending_request_builds(self):
        request = _request()

        self.assertEqual(request.status, ApprovalStatus.PENDING)
        self.assertIsNone(request.decided_at)

    def test_status_values_are_fixed(self):
        self.assertEqual(
            {status.value for status in ApprovalStatus},
            {"pending", "approved", "rejected", "expired", "executed", "failed"},
        )

    def test_invalid_request_id_is_rejected(self):
        for value in ("", "not-a-uuid", None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _request(request_id=value)

    def test_blank_text_fields_are_rejected(self):
        for field in ("principal_id", "capability", "summary"):
            for value in ("", "   ", None):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        _request(**{field: value})

    def test_digest_must_match_arguments(self):
        with self.assertRaises(ValueError):
            _request(arguments_digest=arguments_digest({"other": True}))

    def test_unknown_status_is_rejected(self):
        with self.assertRaises(ValueError):
            _request(status="maybe")

    def test_timestamps_must_be_utc(self):
        local = datetime(2026, 10, 23, 10, 0, tzinfo=timezone(timedelta(hours=1)))
        naive = datetime(2026, 10, 23, 10, 0)
        for field in ("created_at", "expires_at"):
            for value in (local.isoformat(), naive.isoformat(), "yesterday", ""):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        _request(**{field: value})

    def test_expiry_must_follow_creation(self):
        with self.assertRaises(ValueError):
            _request(expires_at=_CREATED.isoformat(timespec="microseconds"))

    def test_pending_request_cannot_have_decision_time(self):
        with self.assertRaises(ValueError):
            _request(decided_at=_CREATED.isoformat(timespec="microseconds"))

    def test_decided_request_requires_decision_time(self):
        for status in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED):
            with self.subTest(status=status):
                with self.assertRaises(ValueError):
                    _request(status=status, decided_at=None)

                decided = _request(
                    status=status,
                    decided_at=(_CREATED + timedelta(minutes=1)).isoformat(
                        timespec="microseconds"
                    ),
                )
                self.assertEqual(decided.status, status)

    def test_outcome_required_only_after_execution(self):
        decided = (_CREATED + timedelta(minutes=1)).isoformat(timespec="microseconds")
        for status in (ApprovalStatus.EXECUTED, ApprovalStatus.FAILED):
            with self.subTest(status=status):
                for outcome in (None, "", "  "):
                    with self.assertRaises(ValueError):
                        _request(status=status, decided_at=decided, outcome=outcome)
                self.assertEqual(
                    _request(status=status, decided_at=decided, outcome="Done.").outcome,
                    "Done.",
                )

        with self.assertRaises(ValueError):
            _request(outcome="Too early.")
        with self.assertRaises(ValueError):
            _request(status=ApprovalStatus.APPROVED, decided_at=decided, outcome="x")

    def test_request_is_immutable(self):
        request = _request()
        with self.assertRaises(Exception):
            request.status = ApprovalStatus.APPROVED

        self.assertEqual(
            replace(
                request,
                status=ApprovalStatus.REJECTED,
                decided_at=_CREATED.isoformat(timespec="microseconds"),
            ).status,
            ApprovalStatus.REJECTED,
        )


if __name__ == "__main__":
    unittest.main()
