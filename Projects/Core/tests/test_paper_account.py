import unittest
from decimal import Decimal

from app.modules.tradingbot.models import OrderSide, PaperOrder
from app.modules.tradingbot.paper_account import PaperAccount


class PaperAccountTests(unittest.TestCase):
    def test_starts_with_virtual_cash_and_no_positions(self):
        account = PaperAccount()

        self.assertEqual(
            account.cash_balance,
            Decimal("10000.00"),
        )
        self.assertEqual(account.positions, {})

    def test_buy_reduces_cash_and_adds_position(self):
        account = PaperAccount()
        order = PaperOrder(
            symbol="btc-gbp",
            side=OrderSide.BUY,
            quantity=Decimal("0.01"),
            price=Decimal("50000"),
        )

        account.apply_order(order)

        self.assertEqual(
            account.cash_balance,
            Decimal("9500.00"),
        )
        self.assertEqual(
            account.position_for("BTC-GBP"),
            Decimal("0.01"),
        )

    def test_rejects_buy_above_available_cash(self):
        account = PaperAccount(
            starting_cash=Decimal("100.00"),
        )
        order = PaperOrder(
            symbol="BTC-GBP",
            side=OrderSide.BUY,
            quantity=Decimal("0.01"),
            price=Decimal("50000"),
        )

        with self.assertRaisesRegex(
            ValueError,
            "exceeds available cash",
        ):
            account.apply_order(order)

        self.assertEqual(
            account.cash_balance,
            Decimal("100.00"),
        )
        self.assertEqual(account.positions, {})

    def test_rejects_sell_without_position(self):
        account = PaperAccount()
        order = PaperOrder(
            symbol="BTC-GBP",
            side=OrderSide.SELL,
            quantity=Decimal("0.01"),
            price=Decimal("50000"),
        )

        with self.assertRaisesRegex(ValueError, "Cannot sell"):
            account.apply_order(order)

        self.assertEqual(account.positions, {})

    def test_sell_releases_cash_and_removes_position(self):
        account = PaperAccount()

        account.apply_order(
            PaperOrder(
                symbol="BTC-GBP",
                side=OrderSide.BUY,
                quantity=Decimal("2"),
                price=Decimal("100"),
            )
        )
        account.apply_order(
            PaperOrder(
                symbol="BTC-GBP",
                side=OrderSide.SELL,
                quantity=Decimal("2"),
                price=Decimal("120"),
            )
        )

        self.assertEqual(
            account.cash_balance,
            Decimal("10040.00"),
        )
        self.assertEqual(account.positions, {})


if __name__ == "__main__":
    unittest.main()