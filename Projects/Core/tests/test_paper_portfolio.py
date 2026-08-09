import unittest
from decimal import Decimal

from app.modules.tradingbot.models import OrderSide, PaperOrder
from app.modules.tradingbot.paper_account import PaperAccount
from app.modules.tradingbot.paper_portfolio import PaperPortfolio
from app.modules.tradingbot.trading_bot import TradingBot


class PaperPortfolioTests(unittest.TestCase):
    def test_empty_portfolio_equals_cash_balance(self):
        portfolio = PaperPortfolio(PaperAccount())

        snapshot = portfolio.snapshot({})

        self.assertEqual(
            snapshot.cash_balance,
            Decimal("10000.00"),
        )
        self.assertEqual(
            snapshot.positions_value,
            Decimal("0"),
        )
        self.assertEqual(
            snapshot.total_value,
            Decimal("10000.00"),
        )

    def test_values_position_using_simulated_price(self):
        account = PaperAccount()
        account.apply_order(
            PaperOrder(
                symbol="BTC-GBP",
                side=OrderSide.BUY,
                quantity=Decimal("2"),
                price=Decimal("100"),
            )
        )
        portfolio = PaperPortfolio(account)

        snapshot = portfolio.snapshot(
            {"btc-gbp": Decimal("120")}
        )

        self.assertEqual(
            snapshot.cash_balance,
            Decimal("9800.00"),
        )
        self.assertEqual(
            snapshot.position_values,
            {"BTC-GBP": Decimal("240")},
        )
        self.assertEqual(
            snapshot.positions_value,
            Decimal("240"),
        )
        self.assertEqual(
            snapshot.total_value,
            Decimal("10040.00"),
        )

    def test_requires_price_for_each_position(self):
        account = PaperAccount()
        account.apply_order(
            PaperOrder(
                symbol="BTC-GBP",
                side=OrderSide.BUY,
                quantity=Decimal("1"),
                price=Decimal("100"),
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "Missing simulated price",
        ):
            PaperPortfolio(account).snapshot({})

    def test_rejects_non_positive_price(self):
        account = PaperAccount()
        account.apply_order(
            PaperOrder(
                symbol="BTC-GBP",
                side=OrderSide.BUY,
                quantity=Decimal("1"),
                price=Decimal("100"),
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "must be positive",
        ):
            PaperPortfolio(account).snapshot(
                {"BTC-GBP": Decimal("0")}
            )

    def test_trading_bot_exposes_portfolio_snapshot(self):
        account = PaperAccount()
        bot = TradingBot(account=account)

        bot.place_paper_order(
            symbol="BTC-GBP",
            side=OrderSide.BUY,
            quantity=Decimal("2"),
            price=Decimal("100"),
        )

        snapshot = bot.paper_portfolio_snapshot(
            {"BTC-GBP": Decimal("120")}
        )

        self.assertEqual(
            snapshot.positions_value,
            Decimal("240"),
        )
        self.assertEqual(
            snapshot.total_value,
            Decimal("10040.00"),
        )


if __name__ == "__main__":
    unittest.main()