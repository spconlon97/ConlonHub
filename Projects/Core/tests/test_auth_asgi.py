import asyncio
import json
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from app.core.auth.credentials import generate_api_key, hash_api_key
from app.core.auth.dependency import get_auth_repository
from app.core.auth.principal import Principal
from app.core.auth.repository import SqliteAuthRepository
from app.main import app


def _make_receive(body=b""):
    sent = False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    return receive


async def _call_asgi(method, path, body=b"", headers=None):
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": headers or [],
        "server": ("testserver", 80),
        "client": ("testclient", 123),
        "scheme": "http",
        "root_path": "",
        "app": app,
    }

    messages = []

    async def send(message):
        messages.append(message)

    await app(scope, _make_receive(body), send)

    start = next(m for m in messages if m["type"] == "http.response.start")
    body = b"".join(
        m.get("body", b"") for m in messages if m["type"] == "http.response.body"
    )

    return start["status"], start["headers"], body


def call_asgi(method, path, body=b"", headers=None):
    return asyncio.run(_call_asgi(method, path, body, headers))


class _FailingRepository:
    def find_credential_by_key_id(self, key_id):
        raise sqlite3.OperationalError("simulated repository failure")

    def get_principal(self, principal_id):
        raise AssertionError("get_principal should not be reached")


_repository_call_count = []


def _repository_must_not_be_called():
    _repository_call_count.append(True)
    raise AssertionError("repository dependency should not be reached")


def _seed_repository(temp_dir, principal_id="p-1", name="Test Principal"):
    database_path = Path(temp_dir) / "auth.db"
    repository = SqliteAuthRepository(database_path)
    principal = Principal(principal_id=principal_id, name=name)
    repository.create_principal(principal)

    issued = generate_api_key()
    verifier = hash_api_key(issued.secret, salt=b"\x00" * 16)
    repository.add_api_key_verifier(issued.key_id, principal_id, verifier)

    return repository, principal, issued.token


def _www_authenticate(headers):
    return [v for k, v in headers if k.lower() == b"www-authenticate"]


class AuthAsgiTests(unittest.TestCase):
    def setUp(self):
        self._original_overrides = dict(app.dependency_overrides)
        _repository_call_count.clear()

    def tearDown(self):
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self._original_overrides)

    # --- 200 -----------------------------------------------------------

    def test_valid_bearer_credential_returns_principal(self):
        with TemporaryDirectory() as temp_dir:
            repository, principal, token = _seed_repository(temp_dir)
            app.dependency_overrides[get_auth_repository] = lambda: repository

            status_code, _headers, body = call_asgi(
                "GET",
                "/auth/whoami",
                headers=[(b"authorization", f"Bearer {token}".encode())],
            )

            self.assertEqual(status_code, 200)
            payload = json.loads(body)
            self.assertEqual(
                payload, {"principal_id": "p-1", "name": "Test Principal"}
            )

    def test_response_contains_only_principal_id_and_name(self):
        with TemporaryDirectory() as temp_dir:
            repository, _principal, token = _seed_repository(temp_dir)
            app.dependency_overrides[get_auth_repository] = lambda: repository

            _status_code, _headers, body = call_asgi(
                "GET",
                "/auth/whoami",
                headers=[(b"authorization", f"Bearer {token}".encode())],
            )

            payload = json.loads(body)
            self.assertEqual(set(payload.keys()), {"principal_id", "name"})

    # --- 401 : HTTPBearer-level failures (repository must never be reached) --

    def test_missing_authorization_header_returns_401(self):
        app.dependency_overrides[get_auth_repository] = _repository_must_not_be_called

        status_code, headers, body = call_asgi("GET", "/auth/whoami")

        self.assertEqual(status_code, 401)
        self.assertEqual(json.loads(body), {"detail": "Not authenticated"})
        self.assertEqual(_www_authenticate(headers), [b"Bearer"])

    def test_missing_authorization_does_not_resolve_repository(self):
        # Distinct from test_missing_authorization_header_returns_401: this
        # test's purpose is specifically to prove the repository dependency
        # is never resolved, not merely that the response happens to be 401.
        app.dependency_overrides[get_auth_repository] = _repository_must_not_be_called

        status_code, _headers, body = call_asgi("GET", "/auth/whoami")

        self.assertEqual(status_code, 401)
        self.assertEqual(json.loads(body), {"detail": "Not authenticated"})
        self.assertEqual(_repository_call_count, [])

    def test_wrong_scheme_returns_401(self):
        app.dependency_overrides[get_auth_repository] = _repository_must_not_be_called

        status_code, headers, body = call_asgi(
            "GET",
            "/auth/whoami",
            headers=[(b"authorization", b"Basic dXNlcjpwYXNz")],
        )

        self.assertEqual(status_code, 401)
        self.assertEqual(json.loads(body), {"detail": "Not authenticated"})
        self.assertEqual(_www_authenticate(headers), [b"Bearer"])
        self.assertEqual(_repository_call_count, [])

    def test_bare_or_malformed_authorization_scheme_returns_401(self):
        app.dependency_overrides[get_auth_repository] = _repository_must_not_be_called

        status_code, headers, body = call_asgi(
            "GET",
            "/auth/whoami",
            headers=[(b"authorization", b"justatokennoscheme")],
        )

        self.assertEqual(status_code, 401)
        self.assertEqual(json.loads(body), {"detail": "Not authenticated"})
        self.assertEqual(_www_authenticate(headers), [b"Bearer"])
        self.assertEqual(_repository_call_count, [])

    # --- 401 : credential-invalid failures (repository-backed) -------------

    def test_malformed_token_returns_401(self):
        with TemporaryDirectory() as temp_dir:
            repository, _principal, _token = _seed_repository(temp_dir)
            app.dependency_overrides[get_auth_repository] = lambda: repository

            status_code, headers, body = call_asgi(
                "GET",
                "/auth/whoami",
                headers=[(b"authorization", b"Bearer not-a-valid-token")],
            )

            self.assertEqual(status_code, 401)
            self.assertEqual(json.loads(body), {"detail": "Not authenticated"})
            self.assertEqual(_www_authenticate(headers), [b"Bearer"])

    def test_unknown_key_id_returns_401(self):
        with TemporaryDirectory() as temp_dir:
            repository, _principal, _token = _seed_repository(temp_dir)
            app.dependency_overrides[get_auth_repository] = lambda: repository

            status_code, headers, body = call_asgi(
                "GET",
                "/auth/whoami",
                headers=[
                    (b"authorization", b"Bearer unknown-key-id-value.some-secret")
                ],
            )

            self.assertEqual(status_code, 401)
            self.assertEqual(json.loads(body), {"detail": "Not authenticated"})
            self.assertEqual(_www_authenticate(headers), [b"Bearer"])

    def test_wrong_secret_returns_401(self):
        with TemporaryDirectory() as temp_dir:
            repository, _principal, token = _seed_repository(temp_dir)
            app.dependency_overrides[get_auth_repository] = lambda: repository

            key_id = token.split(".", 1)[0]
            status_code, headers, body = call_asgi(
                "GET",
                "/auth/whoami",
                headers=[
                    (b"authorization", f"Bearer {key_id}.wrong-secret".encode())
                ],
            )

            self.assertEqual(status_code, 401)
            self.assertEqual(json.loads(body), {"detail": "Not authenticated"})
            self.assertEqual(_www_authenticate(headers), [b"Bearer"])

    def test_all_credential_invalid_cases_share_identical_401_body(self):
        with TemporaryDirectory() as temp_dir:
            repository, _principal, token = _seed_repository(temp_dir)
            app.dependency_overrides[get_auth_repository] = lambda: repository

            key_id = token.split(".", 1)[0]
            scenarios = [
                None,
                [(b"authorization", b"Basic dXNlcjpwYXNz")],
                [(b"authorization", b"Bearer not-a-valid-token")],
                [(b"authorization", b"Bearer unknown-key-id-value.some-secret")],
                [(b"authorization", f"Bearer {key_id}.wrong-secret".encode())],
            ]

            bodies = set()
            for headers in scenarios:
                status_code, _headers, body = call_asgi(
                    "GET", "/auth/whoami", headers=headers
                )
                self.assertEqual(status_code, 401)
                bodies.add(body)

            self.assertEqual(len(bodies), 1)

    # --- 500 -----------------------------------------------------------

    def test_missing_principal_for_valid_credential_returns_500(self):
        with TemporaryDirectory() as temp_dir:
            repository, principal, token = _seed_repository(temp_dir)
            app.dependency_overrides[get_auth_repository] = lambda: repository

            with closing(sqlite3.connect(repository.database_path)) as connection:
                connection.execute(
                    "DELETE FROM principals WHERE principal_id = ?",
                    (principal.principal_id,),
                )
                connection.commit()

            status_code, _headers, body = call_asgi(
                "GET",
                "/auth/whoami",
                headers=[(b"authorization", f"Bearer {token}".encode())],
            )

            self.assertEqual(status_code, 500)
            self.assertEqual(json.loads(body), {"detail": "Internal server error"})

    def test_corrupted_verifier_returns_500(self):
        with TemporaryDirectory() as temp_dir:
            repository, _principal, token = _seed_repository(temp_dir)
            app.dependency_overrides[get_auth_repository] = lambda: repository

            key_id = token.split(".", 1)[0]
            with closing(sqlite3.connect(repository.database_path)) as connection:
                connection.execute(
                    "UPDATE api_keys SET digest = ? WHERE key_id = ?",
                    (b"\x00" * 4, key_id),
                )
                connection.commit()

            status_code, _headers, body = call_asgi(
                "GET",
                "/auth/whoami",
                headers=[(b"authorization", f"Bearer {token}".encode())],
            )

            self.assertEqual(status_code, 500)
            self.assertEqual(json.loads(body), {"detail": "Internal server error"})

    def test_unexpected_repository_failure_returns_500(self):
        app.dependency_overrides[get_auth_repository] = lambda: _FailingRepository()

        status_code, _headers, body = call_asgi(
            "GET",
            "/auth/whoami",
            headers=[(b"authorization", b"Bearer some-key-id.some-secret")],
        )

        self.assertEqual(status_code, 500)
        self.assertEqual(json.loads(body), {"detail": "Internal server error"})

    def test_500_responses_leak_no_credential_or_database_details(self):
        with TemporaryDirectory() as temp_dir:
            repository, _principal, token = _seed_repository(temp_dir)
            key_id = token.split(".", 1)[0]

            # corrupted-verifier scenario
            with closing(sqlite3.connect(repository.database_path)) as connection:
                connection.execute(
                    "UPDATE api_keys SET digest = ? WHERE key_id = ?",
                    (b"\x00" * 4, key_id),
                )
                connection.commit()
            app.dependency_overrides[get_auth_repository] = lambda: repository
            _s1, _h1, body1 = call_asgi(
                "GET",
                "/auth/whoami",
                headers=[(b"authorization", f"Bearer {token}".encode())],
            )

            # unexpected repository failure scenario
            app.dependency_overrides[get_auth_repository] = lambda: _FailingRepository()
            _s2, _h2, body2 = call_asgi(
                "GET",
                "/auth/whoami",
                headers=[(b"authorization", f"Bearer {token}".encode())],
            )

            for body in (body1, body2):
                self.assertEqual(json.loads(body), {"detail": "Internal server error"})
                self.assertNotIn(str(repository.database_path).encode(), body)
                self.assertNotIn(key_id.encode(), body)
                self.assertNotIn(b"simulated repository failure", body)

    # --- existing behaviour untouched ------------------------------------

    def test_existing_routes_remain_unauthenticated_and_unchanged(self):
        for path in ("/", "/modules", "/tradingbot/paper-account", "/ai/status"):
            status_code, _headers, _body = call_asgi("GET", path)
            self.assertEqual(status_code, 200, msg=f"{path} should remain open")


if __name__ == "__main__":
    unittest.main()
