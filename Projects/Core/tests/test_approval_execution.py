import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from app.core.approvals.models import ApprovalStatus
from app.core.approvals.repository import SqliteApprovalRepository
from app.core.approvals.service import approve_and_execute, reject
from app.core.capabilities.models import Capability, CapabilityAccess
from app.core.capabilities.registry import (
    CapabilityNotFound,
    CapabilityRegistry,
    CapabilityRequiresApproval,
)


_START = datetime(2026, 10, 23, 10, 0, tzinfo=timezone.utc)


class FakeClock:
    def __init__(self):
        self.now = _START

    def __call__(self):
        return self.now


def _action(handler, name="example.action", summarize=None):
    return Capability(
        name=name,
        description="Change something.",
        access=CapabilityAccess.ACTION,
        handler=handler,
        summarize=summarize or (lambda **arguments: f"Do {arguments}"),
    )


class CapabilitySummarizeTests(unittest.TestCase):
    def test_action_requires_callable_summarize(self):
        for summarize in (None, "text"):
            with self.subTest(summarize=summarize):
                with self.assertRaises(ValueError):
                    Capability("x", "d", CapabilityAccess.ACTION, lambda: None,
                               summarize=summarize)

    def test_read_must_not_have_summarize(self):
        with self.assertRaises(ValueError):
            Capability("x", "d", CapabilityAccess.READ, lambda: None,
                       summarize=lambda: "s")

    def test_read_without_summarize_builds(self):
        self.assertIsNone(Capability("x", "d", CapabilityAccess.READ, lambda: 1).summarize)


class RegistryAccessCheckTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = TemporaryDirectory()
        self.clock = FakeClock()
        self.repository = SqliteApprovalRepository(
            Path(self._temp_dir.name) / "approvals.db", clock=self.clock
        )
        self.handler = Mock(return_value={"done": True})
        self.registry = CapabilityRegistry()
        self.registry.register(_action(self.handler))

    def tearDown(self):
        self._temp_dir.cleanup()

    def _create(self, capability="example.action", arguments=None):
        return self.repository.create(
            principal_id="p-1",
            capability=capability,
            arguments={"amount": "5"} if arguments is None else arguments,
            summary="Do the thing",
        )

    def test_plain_execute_refuses_action(self):
        with self.assertRaises(CapabilityRequiresApproval):
            self.registry.execute("example.action", amount="5")

        self.handler.assert_not_called()

    def test_plain_execute_still_runs_read(self):
        self.registry.register(
            Capability("example.read", "Read.", CapabilityAccess.READ, lambda: 7)
        )

        self.assertEqual(self.registry.execute("example.read"), 7)

    def test_execute_approved_runs_approved_action_with_stored_arguments(self):
        request = self._create()
        approved = self.repository.decide(request.request_id, "p-1", approve=True)

        result = self.registry.execute_approved(approved)

        self.assertEqual(result, {"done": True})
        self.handler.assert_called_once_with(amount="5")

    def test_execute_approved_refuses_non_approved_requests(self):
        pending = self._create()
        rejected = self.repository.decide(self._create().request_id, "p-1", approve=False)
        expiring = self._create()
        self.clock.now += timedelta(hours=1)
        expired = self.repository.get(expiring.request_id, "p-1")
        self.assertEqual(expired.status, ApprovalStatus.EXPIRED)

        for request in (pending, rejected, expired):
            with self.subTest(status=request.status):
                with self.assertRaises(CapabilityRequiresApproval):
                    self.registry.execute_approved(request)

        self.handler.assert_not_called()

    def test_execute_approved_refuses_tampered_arguments(self):
        approved = self.repository.decide(self._create().request_id, "p-1", approve=True)
        object.__setattr__(approved, "arguments", {"amount": "5000"})

        with self.assertRaises(CapabilityRequiresApproval):
            self.registry.execute_approved(approved)

        self.handler.assert_not_called()

    def test_execute_approved_refuses_missing_or_downgraded_capability(self):
        approved = self.repository.decide(
            self._create(capability="example.gone").request_id, "p-1", approve=True
        )
        with self.assertRaises(CapabilityNotFound):
            self.registry.execute_approved(approved)

        registry = CapabilityRegistry()
        registry.register(
            Capability("example.action", "Now read.", CapabilityAccess.READ, self.handler)
        )
        approved = self.repository.decide(self._create().request_id, "p-1", approve=True)
        with self.assertRaises(CapabilityRequiresApproval):
            registry.execute_approved(approved)

        self.handler.assert_not_called()

    def test_execute_approved_requires_an_approval_request(self):
        with self.assertRaises(TypeError):
            self.registry.execute_approved({"capability": "example.action"})


class ApprovalServiceTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = TemporaryDirectory()
        self.repository = SqliteApprovalRepository(
            Path(self._temp_dir.name) / "approvals.db", clock=FakeClock()
        )
        self.handler = Mock(return_value={"order": "filled"})
        self.registry = CapabilityRegistry()
        self.registry.register(_action(self.handler))

    def tearDown(self):
        self._temp_dir.cleanup()

    def _create(self):
        return self.repository.create(
            principal_id="p-1",
            capability="example.action",
            arguments={"amount": "5"},
            summary="Do the thing",
        )

    def test_approve_executes_once_and_records_executed(self):
        request = self._create()

        result = approve_and_execute(
            self.repository, self.registry, request.request_id, "p-1"
        )

        self.assertEqual(result.status, ApprovalStatus.EXECUTED)
        self.assertEqual(result.outcome, '{"order": "filled"}')
        self.handler.assert_called_once_with(amount="5")
        self.assertEqual(self.repository.get(request.request_id, "p-1"), result)

    def test_none_result_is_recorded_as_executed(self):
        self.handler.return_value = None

        result = approve_and_execute(
            self.repository, self.registry, self._create().request_id, "p-1"
        )

        self.assertEqual(result.outcome, "Executed.")

    def test_second_approval_does_not_execute_again(self):
        request = self._create()
        approve_and_execute(self.repository, self.registry, request.request_id, "p-1")

        from app.core.approvals.repository import ApprovalNotPending
        with self.assertRaises(ApprovalNotPending):
            approve_and_execute(self.repository, self.registry, request.request_id, "p-1")

        self.handler.assert_called_once()

    def test_reject_never_executes(self):
        request = self._create()

        result = reject(self.repository, request.request_id, "p-1")

        self.assertEqual(result.status, ApprovalStatus.REJECTED)
        self.handler.assert_not_called()

    def test_validation_error_is_recorded_as_failed_with_its_message(self):
        self.handler.side_effect = ValueError("Paper order value exceeds maximum.")

        result = approve_and_execute(
            self.repository, self.registry, self._create().request_id, "p-1"
        )

        self.assertEqual(result.status, ApprovalStatus.FAILED)
        self.assertEqual(result.outcome, "Paper order value exceeds maximum.")

    def test_unexpected_error_is_recorded_without_details(self):
        self.handler.side_effect = RuntimeError("secret path C:/x token=abc")

        result = approve_and_execute(
            self.repository, self.registry, self._create().request_id, "p-1"
        )

        self.assertEqual(result.status, ApprovalStatus.FAILED)
        self.assertEqual(result.outcome, "Execution failed.")

    def test_unsafe_request_is_recorded_as_failed(self):
        registry = CapabilityRegistry()

        result = approve_and_execute(
            self.repository, registry, self._create().request_id, "p-1"
        )

        self.assertEqual(result.status, ApprovalStatus.FAILED)
        self.assertEqual(result.outcome, "Approval could not be executed safely.")

    def test_long_outcome_is_truncated(self):
        self.handler.side_effect = ValueError("x" * 2000)

        result = approve_and_execute(
            self.repository, self.registry, self._create().request_id, "p-1"
        )

        self.assertEqual(len(result.outcome), 500)


if __name__ == "__main__":
    unittest.main()
