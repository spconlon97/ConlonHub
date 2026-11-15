import io
import json
import sqlite3
import unittest
from contextlib import closing, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from app.core.auth.phone_devices import (
    MAX_PAIRING_ATTEMPTS,
    PAIRING_CODE_TTL,
    PairingFailed,
    SqlitePhoneDeviceRepository,
)
from app.core.auth.phone_pairing import main as pairing_main
from app.core.database import current_schema_version


_START = datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc)


class FakeClock:
    def __init__(self):
        self.now = _START

    def __call__(self):
        return self.now


class SqlitePhoneDeviceRepositoryTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = TemporaryDirectory()
        self.addCleanup(self._temp_dir.cleanup)
        self.database_path = Path(self._temp_dir.name) / "auth.db"
        self.clock = FakeClock()
        self.repository = SqlitePhoneDeviceRepository(self.database_path, clock=self.clock)

    def _pair(self, principal_id="tailscale:owner", name="Pixel"):
        code = self.repository.create_pairing_code()
        return self.repository.redeem(code, principal_id, name)

    def test_code_is_six_digits_and_expires_after_five_minutes(self):
        code = self.repository.create_pairing_code()

        self.assertRegex(code, r"^\d{6}$")
        self.assertEqual(PAIRING_CODE_TTL, timedelta(minutes=5))

    def test_redeem_returns_random_token_and_device(self):
        device, token = self._pair()

        self.assertGreaterEqual(len(token), 40)
        self.assertEqual(device.principal_id, "tailscale:owner")
        self.assertEqual(device.name, "Pixel")
        self.assertEqual(self.repository.verify(token, "tailscale:owner"), device)

    def test_code_works_only_once(self):
        code = self.repository.create_pairing_code()
        self.repository.redeem(code, "tailscale:owner", "Pixel")

        with self.assertRaises(PairingFailed):
            self.repository.redeem(code, "tailscale:owner", "Pixel")

    def test_code_fails_at_expiry(self):
        code = self.repository.create_pairing_code()
        self.clock.now += PAIRING_CODE_TTL

        with self.assertRaises(PairingFailed):
            self.repository.redeem(code, "tailscale:owner", "Pixel")

    def test_new_code_replaces_unused_old_code(self):
        old = self.repository.create_pairing_code()
        new = self.repository.create_pairing_code()

        with self.assertRaises(PairingFailed):
            self.repository.redeem(old, "tailscale:owner", "Pixel")
        self.repository.redeem(new, "tailscale:owner", "Pixel")

    def test_repeated_wrong_codes_burn_the_active_code(self):
        self.assertEqual(MAX_PAIRING_ATTEMPTS, 5)
        code = self.repository.create_pairing_code()
        wrong = "000000" if code != "000000" else "111111"

        for _ in range(MAX_PAIRING_ATTEMPTS):
            with self.assertRaises(PairingFailed):
                self.repository.redeem(wrong, "tailscale:owner", "Pixel")

        with self.assertRaises(PairingFailed):
            self.repository.redeem(code, "tailscale:owner", "Pixel")

    def test_redeem_without_active_code_fails(self):
        with self.assertRaises(PairingFailed):
            self.repository.redeem("123456", "tailscale:owner", "Pixel")

    def test_malformed_codes_fail(self):
        self.repository.create_pairing_code()

        for code in ("", "12345", "1234567", "abcdef", None, 123456):
            with self.subTest(code=code):
                with self.assertRaises(PairingFailed):
                    self.repository.redeem(code, "tailscale:owner", "Pixel")

    def test_verify_requires_matching_principal_and_live_token(self):
        device, token = self._pair()

        self.assertIsNone(self.repository.verify(token, "tailscale:someone-else"))
        self.assertIsNone(self.repository.verify(token + "x", "tailscale:owner"))
        for value in ("", None, "x" * 500):
            with self.subTest(value=value):
                self.assertIsNone(self.repository.verify(value, "tailscale:owner"))

    def test_revoked_device_no_longer_verifies(self):
        device, token = self._pair()

        self.assertTrue(self.repository.revoke(device.device_id))
        self.assertIsNone(self.repository.verify(token, "tailscale:owner"))
        self.assertFalse(self.repository.revoke(device.device_id))

    def test_device_name_is_cleaned_and_defaulted(self):
        device, _ = self._pair(name="  " + "N" * 100 + "  ")
        self.assertEqual(device.name, "N" * 60)

        device, _ = self._pair(name="   ")
        self.assertEqual(device.name, "Phone")

    def test_list_devices_never_exposes_secrets(self):
        _device, token = self._pair()

        listed = self.repository.list_devices()

        self.assertEqual(len(listed), 1)
        self.assertEqual(
            set(listed[0]), {"device_id", "name", "created_at", "revoked_at"}
        )
        self.assertNotIn(token, json.dumps(listed))

    def test_only_digests_are_stored(self):
        code = self.repository.create_pairing_code()
        _device, token = self.repository.redeem(code, "tailscale:owner", "Pixel")

        with closing(sqlite3.connect(self.database_path)) as connection:
            dump = "\n".join(connection.iterdump())

        self.assertNotIn(token, dump)
        self.assertNotIn(f"'{code}'", dump)

    def test_migration_component_is_recorded(self):
        self.assertEqual(current_schema_version(self.database_path, "phone_devices"), 1)


class PhonePairingCliTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = TemporaryDirectory()
        self.addCleanup(self._temp_dir.cleanup)
        self.database = str(Path(self._temp_dir.name) / "auth.db")

    def _run(self, *args):
        output = io.StringIO()
        with redirect_stdout(output):
            status = pairing_main([*args, "--database", self.database])
        return status, json.loads(output.getvalue())

    def test_new_list_and_revoke(self):
        status, issued = self._run("--new")
        self.assertEqual(status, 0)
        self.assertRegex(issued["code"], r"^\d{6}$")
        self.assertIn("expires_at", issued)

        repository = SqlitePhoneDeviceRepository(self.database)
        device, _token = repository.redeem(issued["code"], "tailscale:owner", "Pixel")

        status, listed = self._run("--list")
        self.assertEqual(status, 0)
        self.assertEqual(listed["devices"][0]["device_id"], device.device_id)

        status, revoked = self._run("--revoke", device.device_id)
        self.assertEqual((status, revoked["revoked"]), (0, True))

        status, revoked = self._run("--revoke", device.device_id)
        self.assertEqual((status, revoked["revoked"]), (1, False))


if __name__ == "__main__":
    unittest.main()
