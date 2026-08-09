import unittest
from decimal import Decimal

from app.modules.tradingbot.models import OrderSide, PaperOrder
from app.modules.tradingbot.paper_pnl import PaperPnlCalculator


class PaperPnlCalculatorTests(unittest.TestCase):
    def setUp(self):
        self.calculator = PaperPnlCalculator()

    def test_calculates_unrealized_profit(self):
        orders = [
            PaperOrder(
                symbol="BTC-GBP",
                side=OrderSide.BUY,
                quantity=Decimal("2"),
                price=Decimal("100"),
            )
        ]

        snapshot = self.calculator.snapshot(
            orders,
            {"BTC-GBP": Decimal("120")},
        )

        self.assertEqual(snapshot.realized_pnl, Decimal("0"))
        self.assertEqual(snapshot.unrealized_pnl, Decimal("40"))
        self.assertEqual(snapshot.total_pnl, Decimal("40"))
        self.assertEqual(
            snapshot.average_costs["BTC-GBP"],
            Decimal("100"),
        )

    def test_calculates_realized_and_unrealized_profit(self):
        orders = [
            PaperOrder(
                symbol="BTC-GBP",
                side=OrderSide.BUY,
                quantity=Decimal("2"),
                price=Decimal("100"),
            ),
            PaperOrder(
                symbol="BTC-GBP",
                side=OrderSide.SELL,
                quantity=Decimal("1"),
                price=Decimal("130"),
            ),
        ]

        snapshot = self.calculator.snapshot(
            orders,
            {"BTC-GBP": Decimal("120")},
        )

        self.assertEqual(snapshot.realized_pnl, Decimal("30"))
        self.assertEqual(snapshot.unrealized_pnl, Decimal("20"))
        self.assertEqual(snapshot.total_pnl, Decimal("50"))

    def test_uses_average_cost_for_multiple_buys(self):
        orders = [
            PaperOrder(
                symbol="ETH-GBP",
                side=OrderSide.BUY,
                quantity=Decimal("1"),
                price=Decimal("100"),
            ),
            PaperOrder(
                symbol="ETH-GBP",
                side=OrderSide.BUY,
                quantity=Decimal("1"),
                price=Decimal("200"),
            ),
        ]

        snapshot = self.calculator.snapshot(
            orders,
            {"ETH-GBP": Decimal("180")},
        )

        self.assertEqual(
            snapshot.average_costs["ETH-GBP"],
            Decimal("150"),
        )
        self.assertEqual(snapshot.unrealized_pnl, Decimal("60"))

    def test_requires_price_for_each_open_position(self):
        orders = [
            PaperOrder(
                symbol="BTC-GBP",
                side=OrderSide.BUY,
                quantity=Decimal("1"),
                price=Decimal("100"),
            )
        ]

        with self.assertRaisesRegex(
            ValueError,
            "Missing simulated price",
        ):
            self.calculator.snapshot(orders, {})

    def test_rejects_non_positive_simulated_price(self):
        orders = [
            PaperOrder(
                symbol="BTC-GBP",
                side=OrderSide.BUY,
                quantity=Decimal("1"),
                price=Decimal("100"),
            )
        ]

        with self.assertRaisesRegex(ValueError, "must be positive"):
            self.calculator.snapshot(
                orders,
                {"BTC-GBP": Decimal("0")},
            )

    def test_rejects_sell_without_sufficient_position(self):
        orders = [
            PaperOrder(
                symbol="BTC-GBP",
                side=OrderSide.SELL,
                quantity=Decimal("1"),
                price=Decimal("100"),
            )
        ]

        with self.assertRaisesRegex(
            ValueError,
            "insufficient BTC-GBP position",
        ):
            self.calculator.snapshot(orders, {})


if __name__ == "__main__":
    unittest.main()