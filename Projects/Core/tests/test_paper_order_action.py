import json
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from app.core.approvals.models import ApprovalStatus
from app.core.approvals.repository import SqliteApprovalRepository
from app.core.approvals.service import approve_and_execute, reject
from app.core.capabilities.builtin import build_capability_registry
from app.core.capabilities.models import CapabilityAccess
from app.modules.ai.orchestration import generate_with_tools
from app.modules.tradingbot.models import OrderSide
from app.modules.tradingbot.trading_bot import TradingBot


_ORDER = {"symbol": "btc-gbp", "side": "buy", "quantity": "0.01", "price": "50000"}


def tool_request(arguments):
    return "MARVIS_TOOL_REQUEST: " + json.dumps(
        {"capability": "trading.place_paper_order", "arguments": arguments}
    )


class PaperOrderCapabilityTests(unittest.TestCase):
    def setUp(self):
        # In-memory TradingBot: no repository, so nothing touches real databases.
        self.trading_bot = TradingBot()
        patcher = patch(
            "app.core.capabilities.builtin.get_module_instance",
            return_value=self.trading_bot,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.capability = build_capability_registry().get("trading.place_paper_order")

    def test_is_the_only_action_capability(self):
        actions = [
            item.name for item in build_capability_registry().list()
            if item.access == CapabilityAccess.ACTION
        ]

        self.assertEqual(actions, ["trading.place_paper_order"])

    def test_summary_describes_buy_and_sell_as_simulated(self):
        self.assertEqual(
            self.capability.summarize(**_ORDER),
            "Paper BUY 0.01 BTC-GBP at 50000 (total 500.00 paper cash). "
            "Simulated only, no real money.",
        )

        self.trading_bot.place_paper_order(
            "ETH-GBP", OrderSide.BUY, Decimal("0.1"), Decimal("2500")
        )
        self.assertEqual(
            self.capability.summarize(
                symbol="ETH-GBP", side="SELL", quantity=0.1, price=2600
            ),
            "Paper SELL 0.1 ETH-GBP at 2600 (total 260.0 paper cash). "
            "Simulated only, no real money.",
        )

    def test_summary_refuses_invalid_orders(self):
        cases = {
            "side": ({**_ORDER, "side": "short"}, "Side must be 'buy' or 'sell'."),
            "symbol": ({**_ORDER, "symbol": "  "}, "Symbol is required."),
            "zero quantity": ({**_ORDER, "quantity": "0"}, "Quantity must be greater than zero."),
            "negative price": ({**_ORDER, "price": "-1"}, "Price must be greater than zero."),
            "not a number": ({**_ORDER, "price": "lots"}, "Price must be a number."),
            "nan": ({**_ORDER, "quantity": "NaN"}, "Quantity must be finite."),
            "bool": ({**_ORDER, "quantity": True}, "Quantity must be a number."),
            "over cap": (
                {**_ORDER, "quantity": "0.1"},
                "Paper order value 5000.0 exceeds maximum of 1000.00.",
            ),
            "no position": ({**_ORDER, "side": "sell"}, None),
        }
        for name, (arguments, message) in cases.items():
            with self.subTest(case=name):
                with self.assertRaises(ValueError) as raised:
                    self.capability.summarize(**arguments)
                if message is not None:
                    self.assertEqual(str(raised.exception), message)

        self.assertEqual(self.trading_bot.list_paper_orders(), ())

    def test_summary_never_places_an_order(self):
        self.capability.summarize(**_ORDER)

        self.assertEqual(self.trading_bot.list_paper_orders(), ())
        self.assertEqual(self.trading_bot.account.cash_balance, Decimal("10000.00"))

    def test_handler_places_one_order_and_returns_json_safe_result(self):
        result = self.capability.handler(**_ORDER)

        self.assertEqual(
            result,
            {
                "order": {
                    "symbol": "BTC-GBP", "side": "buy", "quantity": "0.01",
                    "price": "50000", "status": "filled", "total": "500.00",
                },
                "cash_balance": "9500.00",
            },
        )
        json.dumps(result)
        self.assertEqual(len(self.trading_bot.list_paper_orders()), 1)


class PaperOrderApprovalFlowTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = TemporaryDirectory()
        self.addCleanup(self._temp_dir.cleanup)
        self.approvals = SqliteApprovalRepository(
            Path(self._temp_dir.name) / "approvals.db",
            clock=lambda: datetime(2026, 11, 7, 10, 0, tzinfo=timezone.utc),
        )
        self.trading_bot = TradingBot()
        patcher = patch(
            "app.core.capabilities.builtin.get_module_instance",
            return_value=self.trading_bot,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.registry = build_capability_registry()
        self.provider = Mock()

    def _propose(self, arguments=_ORDER):
        self.provider.generate.side_effect = [tool_request(arguments)]
        return generate_with_tools(
            self.provider, self.registry, "Buy some BTC",
            approvals=self.approvals, principal_id="p-1",
        )

    def test_proposal_then_approval_places_exactly_one_order(self):
        reply = self._propose()

        self.assertTrue(reply.startswith(
            "Approval needed: Paper BUY 0.01 BTC-GBP at 50000"
        ))
        self.assertEqual(self.trading_bot.list_paper_orders(), ())
        (pending,) = self.approvals.list_pending("p-1")

        result = approve_and_execute(
            self.approvals, self.registry, pending.request_id, "p-1"
        )

        self.assertEqual(result.status, ApprovalStatus.EXECUTED)
        self.assertEqual(json.loads(result.outcome)["cash_balance"], "9500.00")
        self.assertEqual(len(self.trading_bot.list_paper_orders()), 1)

    def test_rejection_places_no_order(self):
        self._propose()
        (pending,) = self.approvals.list_pending("p-1")

        reject(self.approvals, pending.request_id, "p-1")

        self.assertEqual(self.trading_bot.list_paper_orders(), ())

    def test_order_no_longer_affordable_at_approval_fails_with_reason(self):
        big = {**_ORDER, "quantity": "0.02"}
        for _ in range(5):
            self._propose(big)
        requests = self.approvals.list_pending("p-1")

        outcomes = [
            approve_and_execute(self.approvals, self.registry, item.request_id, "p-1")
            for item in requests
        ]
        # Cap is 1000 per order; cash covers ten 1000.00 orders, so all five fit.
        self.assertTrue(all(o.status == ApprovalStatus.EXECUTED for o in outcomes))

        self.trading_bot.account.cash_balance = Decimal("100.00")
        self._propose_with_cash_check_bypassed()
        (late,) = self.approvals.list_pending("p-1")
        result = approve_and_execute(self.approvals, self.registry, late.request_id, "p-1")

        self.assertEqual(result.status, ApprovalStatus.FAILED)
        self.assertIn("cash", result.outcome.lower())

    def _propose_with_cash_check_bypassed(self):
        # Create the request directly, as if cash fell after MARVIS proposed it.
        self.approvals.create(
            principal_id="p-1",
            capability="trading.place_paper_order",
            arguments=_ORDER,
            summary="Paper BUY 0.01 BTC-GBP at 50000",
        )

    def test_invalid_order_gets_fixed_refusal_and_creates_nothing(self):
        reply = self._propose({**_ORDER, "quantity": "0.1"})

        self.assertEqual(
            reply,
            "Approval not created: Paper order value 5000.0 exceeds maximum of "
            "1000.00. Nothing has been done.",
        )
        self.assertEqual(self.approvals.list_pending("p-1"), ())
        self.assertEqual(self.trading_bot.list_paper_orders(), ())


if __name__ == "__main__":
    unittest.main()
