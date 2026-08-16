import unittest
from decimal import Decimal

from pathlib import Path
from tempfile import TemporaryDirectory
from app.modules.tradingbot.config import TradingConfig
from app.modules.tradingbot.models import OrderSide, PaperOrder
from app.modules.tradingbot.paper_broker import PaperBroker
from app.modules.tradingbot.trading_bot import TradingBot
from app.modules.tradingbot.sqlite_repository import (
    SqlitePaperOrderRepository,
)



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


class SqlitePaperOrderRepositoryTests(unittest.TestCase):
    def test_persists_and_reloads_order(self):
        with TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "orders.db"
            repository = SqlitePaperOrderRepository(database_path)

            order = PaperOrder(
                symbol="BTC-GBP",
                side=OrderSide.BUY,
                quantity=Decimal("0.01"),
                price=Decimal("50000"),
            )
            repository.add(order)

            reloaded_repository = SqlitePaperOrderRepository(database_path)

            self.assertEqual(
                reloaded_repository.list_all(),
                (order,),
            )

class PaperBrokerPersistenceTests(unittest.TestCase):
    def test_uses_sqlite_repository_when_supplied(self):
        with TemporaryDirectory() as temporary_directory:
            repository = SqlitePaperOrderRepository(
                Path(temporary_directory) / "orders.db"
            )
            broker = PaperBroker(repository=repository)

            order = broker.place_order(
                symbol="btc-gbp",
                side=OrderSide.BUY,
                quantity=Decimal("0.01"),
                price=Decimal("50000"),
            )

            self.assertEqual(broker.list_orders(), (order,))
class TradingBotTests(unittest.TestCase):
    def test_reports_paper_ready(self):
        bot = TradingBot()
        self.assertEqual(bot.version, "0.7.0")

        self.assertEqual(bot.status(), "paper-ready")
        self.assertFalse(bot.config.live_trading_enabled)
    def test_accepts_order_within_value_limit(self):
        bot = TradingBot()

        order = bot.place_paper_order(
            symbol="BTC-GBP",
            side=OrderSide.BUY,
            quantity=Decimal("0.01"),
            price=Decimal("50000"),
        )

        self.assertEqual(order.total, Decimal("500.00"))

    def test_rejects_order_above_value_limit(self):
        bot = TradingBot()

        with self.assertRaisesRegex(ValueError, "exceeds maximum"):
            bot.place_paper_order(
                symbol="BTC-GBP",
                side=OrderSide.BUY,
                quantity=Decimal("0.10"),
                price=Decimal("50000"),
            )

        self.assertEqual(bot.list_paper_orders(), ())

    def test_paper_pnl_snapshot_delegates_to_calculator(self):
        bot = TradingBot()
        bot.place_paper_order(
            symbol="BTC-GBP",
            side=OrderSide.BUY,
            quantity=Decimal("0.01"),
            price=Decimal("50000"),
        )

        snapshot = bot.paper_pnl_snapshot({"BTC-GBP": Decimal("60000")})

        self.assertEqual(snapshot.realized_pnl, Decimal("0"))
        self.assertEqual(snapshot.unrealized_pnl, Decimal("100.00"))
        self.assertEqual(snapshot.total_pnl, Decimal("100.00"))
        self.assertEqual(
            snapshot.average_costs["BTC-GBP"],
            Decimal("50000"),
        )

    def test_paper_pnl_snapshot_requires_price_for_open_position(self):
        bot = TradingBot()
        bot.place_paper_order(
            symbol="BTC-GBP",
            side=OrderSide.BUY,
            quantity=Decimal("0.01"),
            price=Decimal("50000"),
        )

        with self.assertRaisesRegex(ValueError, "Missing simulated price"):
            bot.paper_pnl_snapshot({})


if __name__ == "__main__":
    unittest.main()