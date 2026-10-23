import unittest
from decimal import Decimal
from unittest.mock import Mock, patch

from app.core.capabilities.builtin import build_capability_registry
from app.core.capabilities.models import CapabilityAccess
from app.modules.tradingbot.models import OrderSide, PaperOrder


class BuiltinCapabilityTests(unittest.TestCase):
    def test_registry_contains_expected_read_capabilities(self):
        registry = build_capability_registry()

        expected = {
            "system.modules",
            "trading.status",
            "trading.paper_account",
            "trading.paper_orders",
        }

        self.assertEqual(
            {capability.name for capability in registry.list()},
            expected,
        )

        for capability in registry.list():
            self.assertEqual(capability.access, CapabilityAccess.READ)

    @patch("app.core.capabilities.builtin.get_loaded_modules")
    def test_system_modules_uses_existing_module_loader(self, get_loaded_modules):
        get_loaded_modules.return_value = {
            "modules": {
                "AI Assistant": {
                    "name": "AI Assistant",
                    "version": "0.2.0",
                    "status": "online",
                }
            }
        }

        registry = build_capability_registry()

        result = registry.execute("system.modules")

        self.assertEqual(result, get_loaded_modules.return_value)
        get_loaded_modules.assert_called_once_with()

    @patch("app.core.capabilities.builtin.get_module_instance")
    def test_trading_status_uses_existing_trading_bot(self, get_module_instance):
        trading_bot = Mock()
        trading_bot.name = "Trading Bot"
        trading_bot.version = "0.7.0"
        trading_bot.status.return_value = "paper-ready"
        get_module_instance.return_value = trading_bot

        registry = build_capability_registry()

        result = registry.execute("trading.status")

        self.assertEqual(
            result,
            {
                "name": "Trading Bot",
                "version": "0.7.0",
                "status": "paper-ready",
            },
        )
        get_module_instance.assert_called_once_with("Trading Bot")

    @patch("app.core.capabilities.builtin.get_module_instance")
    def test_trading_paper_account_returns_json_safe_state(
        self, get_module_instance
    ):
        account = Mock()
        account.starting_cash = Decimal("10000.00")
        account.cash_balance = Decimal("9750.00")
        account.positions = {
            "XAUUSD": Decimal("1.25"),
            "GBPUSD": Decimal("2"),
        }

        trading_bot = Mock()
        trading_bot.account = account
        get_module_instance.return_value = trading_bot

        registry = build_capability_registry()

        result = registry.execute("trading.paper_account")

        self.assertEqual(
            result,
            {
                "starting_cash": "10000.00",
                "cash_balance": "9750.00",
                "positions": {
                    "GBPUSD": "2",
                    "XAUUSD": "1.25",
                },
            },
        )

    @patch("app.core.capabilities.builtin.get_module_instance")
    def test_trading_paper_orders_returns_json_safe_orders(
        self, get_module_instance
    ):
        trading_bot = Mock()
        trading_bot.list_paper_orders.return_value = (
            PaperOrder(
                symbol="XAUUSD",
                side=OrderSide.BUY,
                quantity=Decimal("2"),
                price=Decimal("2500.50"),
            ),
        )
        get_module_instance.return_value = trading_bot

        registry = build_capability_registry()

        result = registry.execute("trading.paper_orders")

        self.assertEqual(
            result,
            [
                {
                    "symbol": "XAUUSD",
                    "side": "buy",
                    "quantity": "2",
                    "price": "2500.50",
                    "status": "filled",
                    "total": "5001.00",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
