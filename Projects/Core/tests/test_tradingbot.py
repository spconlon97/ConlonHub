import unittest
from decimal import Decimal

from app.modules.tradingbot.config import TradingConfig
from app.modules.tradingbot.models import OrderSide, PaperOrder
from app.modules.tradingbot.paper_broker import PaperBroker
from app.modules.tradingbot.trading_bot import TradingBot


class TradingConfigTests(unittest.TestCase):
    def test_defaults_to_safe_paper_mode(self):
        config = TradingConfig()

        self.assertEqual(config.mode, "paper")
        self.assertFalse(config.live_trading_enabled)

    def test_rejects_live_trading(self):
        with self.assertRaisesRegex(ValueError, "Live trading is disabled"):
            TradingConfig(live_trading_enabled=True)


class PaperOrderTests(unittest.TestCase):
    def test_calculates_order_total(self):
        order = PaperOrder(
            symbol="BTC-GBP",
            side=OrderSide.BUY,
            quantity=Decimal("0.01"),
            price=Decimal("50000"),
        )

        self.assertEqual(order.total, Decimal("500.00"))

    def test_rejects_zero_quantity(self):
        with self.assertRaisesRegex(
            ValueError,
            "Quantity must be greater than zero",
        ):
            PaperOrder(
                symbol="BTC-GBP",
                side=OrderSide.BUY,
                quantity=Decimal("0"),
                price=Decimal("50000"),
            )


class PaperBrokerTests(unittest.TestCase):
    def test_stores_only_in_memory_and_normalizes_symbol(self):
        broker = PaperBroker()

        order = broker.place_order(
            symbol="btc-gbp",
            side=OrderSide.BUY,
            quantity=Decimal("0.01"),
            price=Decimal("50000"),
        )

        self.assertEqual(order.symbol, "BTC-GBP")
        self.assertEqual(broker.list_orders(), (order,))


class TradingBotTests(unittest.TestCase):
    def test_reports_paper_ready(self):
        bot = TradingBot()

        self.assertEqual(bot.status(), "paper-ready")
        self.assertFalse(bot.config.live_trading_enabled)


if __name__ == "__main__":
    unittest.main()