import hashlib
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.modules.ai import phone as phone_module
from app.modules.ai.router import AIResponseRequest


class FakeRequest:
    def __init__(self, headers=None, host="127.0.0.1"):
        self.headers = headers or {}
        self.client = type("Client", (), {"host": host})()


class PhoneAuthenticationTests(unittest.TestCase):
    def test_requires_tailscale_identity_header(self):
        with self.assertRaises(HTTPException) as raised:
            phone_module.require_tailscale_principal(FakeRequest())

        self.assertEqual(raised.exception.status_code, 401)

    def test_accepts_tailscale_proxy_request_from_non_loopback_client(self):
        request = FakeRequest(
            {"Tailscale-User-Login": "owner@example.com"},
            host="192.168.1.10",
        )

        principal = phone_module.require_tailscale_principal(request)

        self.assertEqual(principal.name, "owner@example.com")

    def test_creates_stable_opaque_principal_from_tailscale_identity(self):
        request = FakeRequest(
            {
                "Tailscale-User-Login": "Owner@Example.com",
                "Tailscale-User-Name": "Sean Paul",
            }
        )

        principal = phone_module.require_tailscale_principal(request)

        expected_digest = hashlib.sha256(b"owner@example.com").hexdigest()
        self.assertEqual(principal.principal_id, f"tailscale:{expected_digest}")
        self.assertEqual(principal.name, "Sean Paul")
        self.assertNotIn("owner@example.com", principal.principal_id)


class PhoneRouterTests(unittest.TestCase):
    def test_phone_routes_are_registered(self):
        routes = {
            (route.path, method)
            for route in phone_module.router.routes
            for method in route.methods
        }

        self.assertIn(("/phone", "GET"), routes)
        self.assertIn(("/phone/api/status", "GET"), routes)
        self.assertIn(("/phone/api/respond", "POST"), routes)

    def test_phone_page_contains_no_remote_assets_or_credentials(self):
        source = Path(phone_module.__file__).with_name("phone.html").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("https://", source)
        self.assertNotIn("Authorization", source)
        self.assertNotIn("api_key", source)
        self.assertIn("/phone/api/respond", source)

    def test_phone_response_reuses_authenticated_ai_handler(self):
        request = AIResponseRequest(prompt="hello")
        principal = phone_module.Principal("tailscale:test", "Test User")
        repository = object()

        with patch.object(
            phone_module,
            "create_ai_response",
            return_value="response",
        ) as create_response:
            result = phone_module.create_phone_response(
                request, principal, repository
            )

        self.assertEqual(result, "response")
        create_response.assert_called_once_with(request, principal, repository)


if __name__ == "__main__":
    unittest.main()
