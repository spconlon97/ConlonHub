import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.core.approvals.dependency import get_approval_repository
from app.core.approvals.repository import SqliteApprovalRepository
from app.core.auth.dependency import get_audit_repository
from app.core.auth.phone_devices import SqlitePhoneDeviceRepository
from app.main import app
from app.modules.ai import phone as phone_module
from app.modules.ai.phone import DEVICE_COOKIE, get_phone_device_repository
from tests.test_asgi_smoke import call_asgi


OWNER_LOGIN = "owner@example.com"
OWNER_PRINCIPAL = "tailscale:" + hashlib.sha256(OWNER_LOGIN.encode()).hexdigest()


def tailscale_headers(login=OWNER_LOGIN):
    return [(b"tailscale-user-login", login.encode())]


def paired_phone_headers(repository, login=OWNER_LOGIN, name="Test phone"):
    """Pair a device directly in the repository and return request headers."""
    principal = "tailscale:" + hashlib.sha256(login.casefold().encode()).hexdigest()
    _device, token = repository.redeem(repository.create_pairing_code(), principal, name)
    return tailscale_headers(login) + [(b"cookie", f"{DEVICE_COOKIE}={token}".encode())]


class RecordingAudit:
    def __init__(self):
        self.events = []

    def record_event(self, **event):
        self.events.append(event)


class PhonePairingRouteTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = TemporaryDirectory()
        self.addCleanup(self._temp_dir.cleanup)
        root = Path(self._temp_dir.name)
        self.devices = SqlitePhoneDeviceRepository(root / "auth.db")
        self.approvals = SqliteApprovalRepository(root / "approvals.db")
        self.audit = RecordingAudit()
        self._original_overrides = dict(app.dependency_overrides)
        self.addCleanup(self._restore_overrides)
        app.dependency_overrides[get_phone_device_repository] = lambda: self.devices
        app.dependency_overrides[get_approval_repository] = lambda: self.approvals
        app.dependency_overrides[get_audit_repository] = lambda: self.audit

    def _restore_overrides(self):
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self._original_overrides)

    def _call(self, method, path, headers=(), body=None):
        headers = list(headers)
        payload = b""
        if body is not None:
            payload = json.dumps(body).encode()
            headers.append((b"content-type", b"application/json"))
        status, response_headers, raw = call_asgi(method, path, payload, headers)
        return status, response_headers, json.loads(raw) if raw else None

    def _pending_request(self):
        return self.approvals.create(
            principal_id=OWNER_PRINCIPAL,
            capability="trading.place_paper_order",
            arguments={"symbol": "BTC-GBP", "side": "buy", "quantity": "0.01", "price": "50000"},
            summary="Paper BUY 0.01 BTC-GBP at 50000",
        )

    # --- unpaired requests ------------------------------------------------

    def test_header_without_device_cookie_is_refused_on_every_phone_api_route(self):
        request = self._pending_request()
        rid = request.request_id

        for method, path, body in (
            ("GET", "/phone/api/status", None),
            ("POST", "/phone/api/respond", {"prompt": "hello"}),
            ("GET", "/phone/api/approvals", None),
            ("GET", f"/phone/api/approvals/{rid}", None),
            ("POST", f"/phone/api/approvals/{rid}/approve", None),
            ("POST", f"/phone/api/approvals/{rid}/reject", None),
        ):
            with self.subTest(method=method, path=path):
                status, _, body_json = self._call(method, path, tailscale_headers(), body)
                self.assertEqual(status, 401)
                self.assertEqual(body_json, {"detail": "Phone pairing required."})

        self.assertEqual(self.approvals.get(rid, OWNER_PRINCIPAL).status.value, "pending")
        self.assertTrue(all(
            e["event_type"] == "phone.authenticate" and e["outcome"] == "rejected"
            for e in self.audit.events
        ))

    def test_forged_header_from_local_program_cannot_approve(self):
        request = self._pending_request()
        forged = tailscale_headers() + [(b"cookie", f"{DEVICE_COOKIE}=guessed".encode())]

        status, _, _ = self._call(
            "POST", f"/phone/api/approvals/{request.request_id}/approve", forged
        )

        self.assertEqual(status, 401)
        self.assertEqual(
            self.approvals.get(request.request_id, OWNER_PRINCIPAL).status.value, "pending"
        )

    def test_page_still_loads_without_pairing(self):
        status, _, _ = call_asgi("GET", "/phone", b"", tailscale_headers())

        self.assertEqual(status, 200)

    def test_missing_tailscale_header_is_still_refused(self):
        status, _, body = self._call("GET", "/phone/api/status")

        self.assertEqual(status, 401)
        self.assertIn("Tailscale", body["detail"])

    # --- pairing ------------------------------------------------------------

    def test_pairing_sets_strict_cookie_and_unlocks_routes(self):
        code = self.devices.create_pairing_code()

        status, headers, body = self._call(
            "POST", "/phone/api/pair", tailscale_headers(),
            {"code": code, "device_name": "Galaxy"},
        )

        self.assertEqual(status, 200)
        self.assertEqual(body, {"paired": True, "device_name": "Galaxy"})
        cookies = [v.decode() for k, v in headers if k.lower() == b"set-cookie"]
        self.assertEqual(len(cookies), 1)
        cookie = cookies[0]
        for flag in ("HttpOnly", "Secure", "SameSite=strict", "Path=/phone"):
            self.assertIn(flag.lower(), cookie.lower())
        token = cookie.split(";", 1)[0].split("=", 1)[1]

        with patch.object(phone_module, "get_module_instance") as get_instance:
            get_instance.return_value.status_details.return_value = {
                "status": "online", "model": "qwen3.5:9b",
            }
            status, _, body = self._call(
                "GET", "/phone/api/status",
                tailscale_headers() + [(b"cookie", f"{DEVICE_COOKIE}={token}".encode())],
            )

        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "online")
        self.assertEqual(self.audit.events[0]["event_type"], "phone.pair")
        self.assertEqual(self.audit.events[0]["outcome"], "success")

    def test_wrong_or_reused_code_is_refused(self):
        code = self.devices.create_pairing_code()
        wrong = "000000" if code != "000000" else "111111"

        status, headers, body = self._call(
            "POST", "/phone/api/pair", tailscale_headers(), {"code": wrong}
        )
        self.assertEqual(status, 400)
        self.assertEqual(body, {"detail": "Pairing code is invalid or expired."})
        self.assertFalse(any(k.lower() == b"set-cookie" for k, _ in headers))

        self._call("POST", "/phone/api/pair", tailscale_headers(), {"code": code})
        status, _, _ = self._call("POST", "/phone/api/pair", tailscale_headers(), {"code": code})
        self.assertEqual(status, 400)
        self.assertEqual(self.audit.events[0]["outcome"], "rejected")

    def test_pairing_requires_tailscale_identity(self):
        code = self.devices.create_pairing_code()

        status, _, _ = self._call("POST", "/phone/api/pair", body={"code": code})

        self.assertEqual(status, 401)

    # --- paired devices -----------------------------------------------------

    def test_paired_phone_can_list_and_approve(self):
        request = self._pending_request()
        headers = paired_phone_headers(self.devices)

        status, _, body = self._call("GET", "/phone/api/approvals", headers)
        self.assertEqual(status, 200)
        self.assertEqual(len(body["approvals"]), 1)

        status, _, body = self._call(
            "POST", f"/phone/api/approvals/{request.request_id}/reject", headers
        )
        self.assertEqual((status, body["status"]), (200, "rejected"))

    def test_cookie_from_another_login_is_refused(self):
        headers = paired_phone_headers(self.devices, login="someone@example.com")
        cookie = [h for h in headers if h[0] == b"cookie"]

        status, _, _ = self._call("GET", "/phone/api/approvals", tailscale_headers() + cookie)

        self.assertEqual(status, 401)

    def test_revoked_device_is_refused(self):
        headers = paired_phone_headers(self.devices)
        (device,) = self.devices.list_devices()
        self.devices.revoke(device["device_id"])

        status, _, _ = self._call("GET", "/phone/api/approvals", headers)

        self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()
