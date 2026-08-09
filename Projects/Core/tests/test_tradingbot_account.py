import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from app.modules.tradingbot.config import TradingConfig
from app.modules.tradingbot.models import OrderSide
from app.modules.tradingbot.paper_broker import PaperBroker
from app.modules.tradingbot.sqlite_repository import (
    SqlitePaperOrderRepository,
)
from app.modules.tradingbot.trading_bot import TradingBot


class TradingBotAccountTests(unittest.TestCase):
    def test_uses_configured_starting_cash(self):
        config = TradingConfig(
            starting_cash=Decimal("250.00"),
        )

        bot = TradingBot(config=config)

        self.assertEqual(
            bot.account.cash_balance,
            Decimal("250.00"),
        )

    def test_accepted_buy_updates_account(self):
        bot = TradingBot()

        order = bot.place_paper_order(
            symbol="BTC-GBP",
            side=OrderSide.BUY,
            quantity=Decimal("0.01"),
            price=Decimal("50000"),
        )

        self.assertEqual(
            bot.account.cash_balance,
            Decimal("9500.00"),
        )
        self.assertEqual(
            bot.account.position_for("BTC-GBP"),
            Decimal("0.01"),
        )
        self.assertEqual(bot.list_paper_orders(), (order,))

    def test_rejects_buy_above_available_cash(self):
        config = TradingConfig(
            starting_cash=Decimal("100.00"),
        )
        bot = TradingBot(config=config)

        with self.assertRaisesRegex(
            ValueError,
            "exceeds available cash",
        ):
            bot.place_paper_order(
                symbol="BTC-GBP",
                side=OrderSide.BUY,
                quantity=Decimal("0.01"),
                price=Decimal("50000"),
            )

        self.assertEqual(bot.list_paper_orders(), ())
        self.assertEqual(
            bot.account.cash_balance,
            Decimal("100.00"),
        )

    def test_rejects_sell_without_position(self):
        bot = TradingBot()

        with self.assertRaisesRegex(ValueError, "Cannot sell"):
            bot.place_paper_order(
                symbol="BTC-GBP",
                side=OrderSide.SELL,
                quantity=Decimal("1"),
                price=Decimal("100"),
            )

        self.assertEqual(bot.list_paper_orders(), ())

    def test_replays_persisted_orders_into_account(self):
        with TemporaryDirectory() as temporary_directory:
            database_path = (
                Path(temporary_directory) / "orders.db"
            )
            repository = SqlitePaperOrderRepository(database_path)
            broker = PaperBroker(repository=repository)

            broker.place_order(
                symbol="BTC-GBP",
                side=OrderSide.BUY,
                quantity=Decimal("0.01"),
                price=Decimal("50000"),
            )

            reloaded_bot = TradingBot(
                broker=PaperBroker(
                    repository=SqlitePaperOrderRepository(
                        database_path
                    )
                )
            )

            self.assertEqual(
                reloaded_bot.account.cash_balance,
                Decimal("9500.00"),
            )
            self.assertEqual(
                reloaded_bot.account.position_for("BTC-GBP"),
                Decimal("0.01"),
            )


if __name__ == "__main__":
    unittest.main()