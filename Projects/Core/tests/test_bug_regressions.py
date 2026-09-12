import io
import json
import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, redirect_stdout
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest.mock import Mock, patch

from app.core.auth.credentials import hash_api_key
from app.core.auth.dependency import require_principal
from app.core.auth.principal import Principal
from app.core.auth.repository import SqliteAuthRepository
from app.core.auth.revoke import main as revoke_main
from app.core.database import migrations
from app.main import app
from app.modules.ai import router as ai_router
from app.modules.tradingbot.config import TradingConfig
from app.modules.tradingbot.models import OrderSide, PaperOrder
from app.modules.tradingbot.paper_account import PaperAccount
from app.modules.tradingbot.paper_pnl import PaperPnlCalculator
from app.modules.tradingbot.paper_portfolio import PaperPortfolio
from tests.test_asgi_smoke import call_asgi


class ChatInputRegressionTests(unittest.TestCase):
    def test_blank_prompt_is_rejected_before_quota_or_provider_call(self):
        repository = Mock()
        assistant = Mock()
        assistant.respond.side_effect = ValueError("prompt must be a non-empty string.")
        overrides = dict(app.dependency_overrides)
        try:
            app.dependency_overrides[require_principal] = lambda: Principal("p", "Test")
            app.dependency_overrides[ai_router.get_ai_conversation_repository] = lambda: repository
            with patch.object(ai_router, "get_module_instance", return_value=assistant):
                for prompt in ("", "   ", "\t\n", "\u2003"):
                    with self.subTest(prompt=repr(prompt)):
                        status, _, _ = call_asgi(
                            "POST", "/ai/respond",
                            json.dumps({"prompt": prompt}).encode(),
                            [(b"content-type", b"application/json")],
                        )
                        self.assertEqual(status, 422)
            repository.claim_request_quota.assert_not_called()
            assistant.respond.assert_not_called()
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(overrides)


class RevocationRegressionTests(unittest.TestCase):
    def test_hyphen_prefixed_key_can_be_revoked(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "auth.db"
            repository = SqliteAuthRepository(path)
            key_id = "-example_key_id12"
            repository.create_principal_with_api_key(
                Principal("p", "Test"), key_id, hash_api_key("test-secret")
            )
            with redirect_stdout(io.StringIO()):
                result = revoke_main(["--key-id", key_id, "--database", str(path)])
            self.assertEqual(result, 0)
            self.assertIsNone(repository.find_credential_by_key_id(key_id))


class MigrationRegressionTests(unittest.TestCase):
    def test_failed_migration_rolls_back_schema_and_can_be_retried(self):
        def failed_migration(connection):
            connection.execute("CREATE TABLE partial_data (value TEXT)")
            raise RuntimeError("interrupted migration")

        with TemporaryDirectory() as directory:
            path = Path(directory) / "core.db"
            with patch.dict(migrations._MIGRATIONS, {"auth": ((1, "failure", failed_migration),)}):
                with self.assertRaisesRegex(RuntimeError, "interrupted"):
                    migrations.migrate_database(path, "auth")
            with closing(sqlite3.connect(path)) as connection:
                self.assertIsNone(connection.execute(
                    "SELECT name FROM sqlite_master WHERE name = 'partial_data'"
                ).fetchone())
            self.assertEqual(migrations.migrate_database(path, "auth"), 1)

    def test_simultaneous_initialization_succeeds(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "core.db"
            barrier = Barrier(8)

            def initialize(_):
                barrier.wait(timeout=5)
                return migrations.migrate_database(path, "ai")

            with ThreadPoolExecutor(max_workers=8) as executor:
                self.assertEqual(list(executor.map(initialize, range(8))), [2] * 8)
            with closing(sqlite3.connect(path)) as connection:
                self.assertEqual(connection.execute(
                    "SELECT COUNT(*) FROM schema_migrations WHERE component = 'ai'"
                ).fetchone()[0], 2)


class PaperDecimalRegressionTests(unittest.TestCase):
    invalid_values = ("NaN", "sNaN", "Infinity", "-Infinity")

    def test_nonfinite_order_values_are_rejected(self):
        for field in ("quantity", "price"):
            for value in self.invalid_values:
                with self.subTest(field=field, value=value):
                    values = {"quantity": Decimal("1"), "price": Decimal("10")}
                    values[field] = Decimal(value)
                    with self.assertRaises(ValueError):
                        PaperOrder("TEST-GBP", OrderSide.BUY, **values)

    def test_nonfinite_account_and_limits_are_rejected(self):
        for value in self.invalid_values:
            for factory in (
                lambda: PaperAccount(starting_cash=Decimal(value)),
                lambda: TradingConfig(starting_cash=Decimal(value)),
                lambda: TradingConfig(max_order_value=Decimal(value)),
            ):
                with self.subTest(value=value, factory=factory):
                    with self.assertRaises(ValueError):
                        factory()

    def test_nonfinite_valuation_prices_are_rejected(self):
        order = PaperOrder("TEST-GBP", OrderSide.BUY, Decimal("1"), Decimal("10"))
        account = PaperAccount()
        account.apply_order(order)
        for value in self.invalid_values:
            for calculate in (
                lambda prices: PaperPortfolio(account).snapshot(prices),
                lambda prices: PaperPnlCalculator().snapshot((order,), prices),
            ):
                with self.subTest(value=value, calculate=calculate):
                    with self.assertRaises(ValueError):
                        calculate({"TEST-GBP": Decimal(value)})


if __name__ == "__main__":
    unittest.main()
