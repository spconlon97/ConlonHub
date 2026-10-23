import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from app.core.approvals.dependency import get_approval_repository
from app.core.approvals.repository import SqliteApprovalRepository
from app.core.approvals.router import get_capability_registry
from app.core.auth.dependency import get_audit_repository, require_principal
from app.core.auth.principal import Principal
from app.core.capabilities.models import Capability, CapabilityAccess
from app.core.capabilities.registry import CapabilityRegistry
from app.main import app
from tests.test_asgi_smoke import call_asgi


_PHONE_LOGIN = "owner@example.com"
_PHONE_PRINCIPAL = "tailscale:" + hashlib.sha256(_PHONE_LOGIN.encode()).hexdigest()
_PHONE_HEADERS = [(b"tailscale-user-login", _PHONE_LOGIN.encode())]


class RecordingAudit:
    def __init__(self):
        self.events = []

    def record_event(self, **event):
        self.events.append(event)


class ApprovalEndpointTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = TemporaryDirectory()
        self.repository = SqliteApprovalRepository(
            Path(self._temp_dir.name) / "approvals.db"
        )
        self.handler = Mock(return_value={"order": "filled"})
        self.registry = CapabilityRegistry()
        self.registry.register(Capability(
            "example.transfer", "Move paper cash", CapabilityAccess.ACTION,
            self.handler, summarize=lambda amount: f"Move {amount}",
        ))
        self.audit = RecordingAudit()
        self._original_overrides = dict(app.dependency_overrides)
        app.dependency_overrides[get_approval_repository] = lambda: self.repository
        app.dependency_overrides[get_capability_registry] = lambda: self.registry
        app.dependency_overrides[get_audit_repository] = lambda: self.audit
        app.dependency_overrides[require_principal] = lambda: Principal("p-1", "Owner")

    def tearDown(self):
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self._original_overrides)
        self._temp_dir.cleanup()

    def _create(self, principal_id="p-1"):
        return self.repository.create(
            principal_id=principal_id,
            capability="example.transfer",
            arguments={"amount": "5"},
            summary="Move 5",
        )

    def _call(self, method, path, headers=None):
        status, _headers, body = call_asgi(method, path, headers=headers)
        return status, json.loads(body) if body else None

    # --- bearer routes ------------------------------------------------------

    def test_list_pending_returns_own_requests(self):
        mine = self._create()
        self._create(principal_id="p-2")

        status, body = self._call("GET", "/approvals")

        self.assertEqual(status, 200)
        self.assertEqual([item["request_id"] for item in body["approvals"]], [mine.request_id])
        item = body["approvals"][0]
        self.assertEqual(item["summary"], "Move 5")
        self.assertEqual(item["arguments"], {"amount": "5"})
        self.assertEqual(item["status"], "pending")

    def test_get_one_and_other_principal_gets_404(self):
        mine = self._create()
        theirs = self._create(principal_id="p-2")

        status, body = self._call("GET", f"/approvals/{mine.request_id}")
        self.assertEqual(status, 200)
        self.assertEqual(body["request_id"], mine.request_id)

        status, body = self._call("GET", f"/approvals/{theirs.request_id}")
        self.assertEqual(status, 404)
        self.assertEqual(body, {"detail": "Approval request was not found."})

    def test_approve_executes_once_and_audits(self):
        request = self._create()

        status, body = self._call("POST", f"/approvals/{request.request_id}/approve")

        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "executed")
        self.assertEqual(body["outcome"], '{"order": "filled"}')
        self.handler.assert_called_once_with(amount="5")
        self.assertEqual(
            [(e["event_type"], e["outcome"], e["principal_id"]) for e in self.audit.events],
            [("approval.approve", "success", "p-1")],
        )
        self.assertEqual(self.audit.events[0]["path"],
                         f"/approvals/{request.request_id}/approve")

        status, body = self._call("POST", f"/approvals/{request.request_id}/approve")
        self.assertEqual(status, 409)
        self.handler.assert_called_once()
        self.assertEqual(self.audit.events[-1]["outcome"], "rejected")

    def test_reject_runs_nothing(self):
        request = self._create()

        status, body = self._call("POST", f"/approvals/{request.request_id}/reject")

        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "rejected")
        self.handler.assert_not_called()
        self.assertEqual(self.audit.events[-1]["event_type"], "approval.reject")

        status, _ = self._call("POST", f"/approvals/{request.request_id}/approve")
        self.assertEqual(status, 409)
        self.handler.assert_not_called()

    def test_failed_execution_returns_failed_without_details(self):
        self.handler.side_effect = RuntimeError("internal secret")
        request = self._create()

        status, body = self._call("POST", f"/approvals/{request.request_id}/approve")

        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "failed")
        self.assertEqual(body["outcome"], "Execution failed.")
        self.assertNotIn("secret", json.dumps(body))
        self.assertEqual(self.audit.events[-1]["outcome"], "error")

    def test_other_principal_cannot_approve(self):
        theirs = self._create(principal_id="p-2")

        status, _ = self._call("POST", f"/approvals/{theirs.request_id}/approve")

        self.assertEqual(status, 404)
        self.handler.assert_not_called()

    def test_audit_failure_does_not_block_decision(self):
        class FailingAudit:
            def record_event(self, **_event):
                raise ValueError("audit down")

        app.dependency_overrides[get_audit_repository] = lambda: FailingAudit()
        request = self._create()

        status, body = self._call("POST", f"/approvals/{request.request_id}/reject")

        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "rejected")

    def test_bearer_routes_require_authentication(self):
        del app.dependency_overrides[require_principal]
        request = self._create()

        for method, path in (
            ("GET", "/approvals"),
            ("GET", f"/approvals/{request.request_id}"),
            ("POST", f"/approvals/{request.request_id}/approve"),
            ("POST", f"/approvals/{request.request_id}/reject"),
        ):
            with self.subTest(method=method, path=path):
                status, body = self._call(method, path)
                self.assertEqual(status, 401)

        self.handler.assert_not_called()
        self.assertEqual(self.repository.get(request.request_id, "p-1").status.value, "pending")

    # --- phone routes -------------------------------------------------------

    def test_phone_routes_use_tailscale_identity(self):
        request = self._create(principal_id=_PHONE_PRINCIPAL)
        bearer_request = self._create()

        status, body = self._call("GET", "/phone/api/approvals", headers=_PHONE_HEADERS)
        self.assertEqual(status, 200)
        self.assertEqual([i["request_id"] for i in body["approvals"]], [request.request_id])

        status, _ = self._call(
            "POST", f"/phone/api/approvals/{bearer_request.request_id}/approve",
            headers=_PHONE_HEADERS,
        )
        self.assertEqual(status, 404)

        status, body = self._call(
            "POST", f"/phone/api/approvals/{request.request_id}/approve",
            headers=_PHONE_HEADERS,
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "executed")
        self.handler.assert_called_once_with(amount="5")
        self.assertEqual(self.audit.events[-1]["principal_id"], _PHONE_PRINCIPAL)

    def test_phone_reject_and_get(self):
        request = self._create(principal_id=_PHONE_PRINCIPAL)

        status, body = self._call(
            "GET", f"/phone/api/approvals/{request.request_id}", headers=_PHONE_HEADERS
        )
        self.assertEqual(status, 200)

        status, body = self._call(
            "POST", f"/phone/api/approvals/{request.request_id}/reject",
            headers=_PHONE_HEADERS,
        )
        self.assertEqual(body["status"], "rejected")
        self.handler.assert_not_called()

    def test_phone_routes_require_tailscale_identity(self):
        request = self._create(principal_id=_PHONE_PRINCIPAL)

        for method, path in (
            ("GET", "/phone/api/approvals"),
            ("POST", f"/phone/api/approvals/{request.request_id}/approve"),
        ):
            with self.subTest(path=path):
                status, _ = self._call(method, path)
                self.assertEqual(status, 401)

        self.handler.assert_not_called()


if __name__ == "__main__":
    unittest.main()
