"""Genuine ASGI-level smoke tests.

These drive the assembled FastAPI app (app.main.app) directly as an ASGI3
callable, using only stdlib asyncio plus the already-installed fastapi/
starlette that provide the app object itself. No httpx, no TestClient, no
network socket.

Limitation: app/main.py currently defines no FastAPI `lifespan`/on_event
handlers, so these tests never send the ASGI "lifespan" protocol messages
(lifespan.startup / lifespan.startup.complete) before issuing HTTP scope
requests. If lifespan/startup logic is introduced later, this harness must
be extended to drive that protocol first, or it will silently skip real
startup behaviour and give a false pass.
"""

import asyncio
import json
import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

from app.core import registry
from app.core.config import settings
from app.main import app
from app.modules import loader
from app.modules.tradingbot import router as tradingbot_router
from app.modules.tradingbot.models import OrderSide
from app.modules.tradingbot.trading_bot import TradingBot


def _make_receive(body=b""):
    sent = False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    return receive


async def _call_asgi(method, path, body=b"", headers=None):
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": headers or [],
        "server": ("testserver", 80),
        "client": ("testclient", 123),
        "scheme": "http",
        "root_path": "",
        "app": app,
    }

    messages = []

    async def send(message):
        messages.append(message)

    await app(scope, _make_receive(body), send)

    start = next(m for m in messages if m["type"] == "http.response.start")
    body = b"".join(
        m.get("body", b"") for m in messages if m["type"] == "http.response.body"
    )

    return start["status"], start["headers"], body


def call_asgi(method, path, body=b"", headers=None):
    return asyncio.run(_call_asgi(method, path, body, headers))


class AsgiSmokeTests(unittest.TestCase):
    def setUp(self):
        self._original_loaded_modules = dict(loader.loaded_modules)
        self._original_module_instances = dict(loader.module_instances)
        loader.loaded_modules.clear()
        loader.module_instances.clear()

    def tearDown(self):
        loader.loaded_modules.clear()
        loader.loaded_modules.update(self._original_loaded_modules)
        loader.module_instances.clear()
        loader.module_instances.update(self._original_module_instances)

    def test_ai_status_responds_over_asgi(self):
        status, headers, body = call_asgi("GET", "/ai/status")

        content_types = [
            value.decode()
            for name, value in headers
            if name.decode().lower() == "content-type"
        ]

        self.assertEqual(status, 200)
        self.assertTrue(
            any(ct.startswith("application/json") for ct in content_types)
        )
        self.assertEqual(
            json.loads(body),
            {
                "name": "AI Assistant",
                "version": "0.1.0",
                "status": "configuration-required",
                "provider": "unconfigured",
                "model": None,
            },
        )

    def test_ai_response_requires_authentication_over_asgi(self):
        status, headers, body = call_asgi(
            "POST",
            "/ai/respond",
            body=json.dumps({"prompt": "hello"}).encode(),
            headers=[(b"content-type", b"application/json")],
        )

        self.assertEqual(status, 401)
        self.assertEqual(json.loads(body), {"detail": "Not authenticated"})
        self.assertIn(
            (b"www-authenticate", b"Bearer"),
            [(name.lower(), value) for name, value in headers],
        )

    def test_ai_conversation_controls_require_authentication_over_asgi(self):
        for method in ("GET", "DELETE"):
            status, headers, body = call_asgi(
                method, "/ai/conversations/conversation-1"
            )

            self.assertEqual(status, 401)
            self.assertEqual(json.loads(body), {"detail": "Not authenticated"})
            self.assertIn(
                (b"www-authenticate", b"Bearer"),
                [(name.lower(), value) for name, value in headers],
            )

        status, _headers, body = call_asgi("GET", "/ai/conversations")
        self.assertEqual(status, 401)
        self.assertEqual(json.loads(body), {"detail": "Not authenticated"})

    def test_unknown_path_returns_404_over_asgi(self):
        status, _headers, _body = call_asgi("GET", "/does-not-exist")

        self.assertEqual(status, 404)

    def test_paper_account_responds_over_asgi_using_authoritative_instance(self):
        status, headers, body = call_asgi("GET", "/tradingbot/paper-account")

        account = tradingbot_router.trading_bot.account
        expected = {
            "starting_cash": str(account.starting_cash),
            "cash_balance": str(account.cash_balance),
            "positions": {
                symbol: str(quantity)
                for symbol, quantity in sorted(account.positions.items())
            },
        }

        content_types = [
            value.decode()
            for name, value in headers
            if name.decode().lower() == "content-type"
        ]

        self.assertEqual(status, 200)
        self.assertTrue(
            any(ct.startswith("application/json") for ct in content_types)
        )
        self.assertEqual(json.loads(body), expected)

    def test_paper_pnl_responds_over_asgi_using_isolated_instance(self):
        isolated_trading_bot = TradingBot()
        self.assertIsNone(isolated_trading_bot.broker.repository)

        isolated_trading_bot.place_paper_order(
            symbol="BTC-GBP",
            side=OrderSide.BUY,
            quantity=Decimal("0.01"),
            price=Decimal("50000"),
        )

        original_trading_bot = tradingbot_router.trading_bot
        original_orders = original_trading_bot.list_paper_orders()

        prices = {"BTC-GBP": Decimal("60000")}
        payload = json.dumps(
            {"prices": {symbol: str(price) for symbol, price in prices.items()}}
        ).encode()

        with patch.object(tradingbot_router, "trading_bot", isolated_trading_bot):
            status, headers, body = call_asgi(
                "POST",
                "/tradingbot/paper-pnl",
                body=payload,
                headers=[(b"content-type", b"application/json")],
            )

        expected_snapshot = isolated_trading_bot.paper_pnl_snapshot(prices)
        expected = {
            "pnl": {
                "realized_pnl": str(expected_snapshot.realized_pnl),
                "unrealized_pnl": str(expected_snapshot.unrealized_pnl),
                "total_pnl": str(expected_snapshot.total_pnl),
                "average_costs": {
                    symbol: str(value)
                    for symbol, value in sorted(
                        expected_snapshot.average_costs.items()
                    )
                },
            }
        }

        content_types = [
            value.decode()
            for name, value in headers
            if name.decode().lower() == "content-type"
        ]

        self.assertEqual(status, 200)
        self.assertTrue(
            any(ct.startswith("application/json") for ct in content_types)
        )
        self.assertEqual(json.loads(body), expected)
        self.assertEqual(
            expected,
            {
                "pnl": {
                    "realized_pnl": "0",
                    "unrealized_pnl": "100.00",
                    "total_pnl": "100.00",
                    "average_costs": {"BTC-GBP": "50000"},
                }
            },
        )

        self.assertIs(tradingbot_router.trading_bot, original_trading_bot)
        self.assertEqual(
            tradingbot_router.trading_bot.list_paper_orders(),
            original_orders,
        )

    def test_paper_pnl_rejects_missing_price_over_asgi(self):
        isolated_trading_bot = TradingBot()
        self.assertIsNone(isolated_trading_bot.broker.repository)

        isolated_trading_bot.place_paper_order(
            symbol="BTC-GBP",
            side=OrderSide.BUY,
            quantity=Decimal("0.01"),
            price=Decimal("50000"),
        )

        original_trading_bot = tradingbot_router.trading_bot
        original_orders = original_trading_bot.list_paper_orders()

        payload = json.dumps({"prices": {}}).encode()

        with patch.object(tradingbot_router, "trading_bot", isolated_trading_bot):
            status, headers, body = call_asgi(
                "POST",
                "/tradingbot/paper-pnl",
                body=payload,
                headers=[(b"content-type", b"application/json")],
            )

        with self.assertRaises(ValueError) as raised:
            isolated_trading_bot.paper_pnl_snapshot({})
        expected_detail = str(raised.exception)

        content_types = [
            value.decode()
            for name, value in headers
            if name.decode().lower() == "content-type"
        ]

        self.assertEqual(status, 400)
        self.assertTrue(
            any(ct.startswith("application/json") for ct in content_types)
        )
        self.assertEqual(expected_detail, "Missing simulated price for BTC-GBP.")
        self.assertEqual(json.loads(body), {"detail": expected_detail})

        self.assertIs(tradingbot_router.trading_bot, original_trading_bot)
        self.assertEqual(
            tradingbot_router.trading_bot.list_paper_orders(),
            original_orders,
        )

    def test_paper_portfolio_rejects_missing_price_over_asgi(self):
        isolated_trading_bot = TradingBot()
        self.assertIsNone(isolated_trading_bot.broker.repository)

        isolated_trading_bot.place_paper_order(
            symbol="BTC-GBP",
            side=OrderSide.BUY,
            quantity=Decimal("0.01"),
            price=Decimal("50000"),
        )

        original_trading_bot = tradingbot_router.trading_bot
        original_orders = original_trading_bot.list_paper_orders()

        payload = json.dumps({"prices": {}}).encode()

        with patch.object(tradingbot_router, "trading_bot", isolated_trading_bot):
            status, headers, body = call_asgi(
                "POST",
                "/tradingbot/paper-portfolio",
                body=payload,
                headers=[(b"content-type", b"application/json")],
            )

        with self.assertRaises(ValueError) as raised:
            isolated_trading_bot.paper_portfolio_snapshot({})
        expected_detail = str(raised.exception)

        content_types = [
            value.decode()
            for name, value in headers
            if name.decode().lower() == "content-type"
        ]

        self.assertEqual(status, 400)
        self.assertTrue(
            any(ct.startswith("application/json") for ct in content_types)
        )
        self.assertEqual(expected_detail, "Missing simulated price for BTC-GBP.")
        self.assertEqual(json.loads(body), {"detail": expected_detail})

        self.assertIs(tradingbot_router.trading_bot, original_trading_bot)
        self.assertEqual(
            tradingbot_router.trading_bot.list_paper_orders(),
            original_orders,
        )

    def test_paper_order_placement_succeeds_over_asgi_using_isolated_instance(self):
        isolated_trading_bot = TradingBot()
        self.assertIsNone(isolated_trading_bot.broker.repository)

        original_trading_bot = tradingbot_router.trading_bot
        original_orders = original_trading_bot.list_paper_orders()

        payload = json.dumps(
            {
                "symbol": "BTC-GBP",
                "side": "buy",
                "quantity": "0.01",
                "price": "50000",
            }
        ).encode()

        with patch.object(tradingbot_router, "trading_bot", isolated_trading_bot):
            status, headers, body = call_asgi(
                "POST",
                "/tradingbot/paper-orders",
                body=payload,
                headers=[(b"content-type", b"application/json")],
            )

        content_types = [
            value.decode()
            for name, value in headers
            if name.decode().lower() == "content-type"
        ]

        self.assertEqual(status, 200)
        self.assertTrue(
            any(ct.startswith("application/json") for ct in content_types)
        )
        self.assertEqual(
            json.loads(body),
            {
                "order": {
                    "symbol": "BTC-GBP",
                    "side": "buy",
                    "quantity": "0.01",
                    "price": "50000",
                    "status": "filled",
                    "total": "500.00",
                }
            },
        )

        self.assertEqual(len(isolated_trading_bot.list_paper_orders()), 1)
        self.assertEqual(
            isolated_trading_bot.list_paper_orders()[0].symbol,
            "BTC-GBP",
        )

        self.assertIs(tradingbot_router.trading_bot, original_trading_bot)
        self.assertEqual(
            tradingbot_router.trading_bot.list_paper_orders(),
            original_orders,
        )

    def test_paper_order_placement_rejected_over_asgi_using_isolated_instance(self):
        isolated_trading_bot = TradingBot()
        self.assertIsNone(isolated_trading_bot.broker.repository)

        original_trading_bot = tradingbot_router.trading_bot
        original_orders = original_trading_bot.list_paper_orders()

        payload = json.dumps(
            {
                "symbol": "BTC-GBP",
                "side": "buy",
                "quantity": "0.10",
                "price": "50000",
            }
        ).encode()

        with patch.object(tradingbot_router, "trading_bot", isolated_trading_bot):
            status, headers, body = call_asgi(
                "POST",
                "/tradingbot/paper-orders",
                body=payload,
                headers=[(b"content-type", b"application/json")],
            )

        content_types = [
            value.decode()
            for name, value in headers
            if name.decode().lower() == "content-type"
        ]

        self.assertEqual(status, 400)
        self.assertTrue(
            any(ct.startswith("application/json") for ct in content_types)
        )
        self.assertIn("exceeds maximum", json.loads(body)["detail"])

        self.assertEqual(isolated_trading_bot.list_paper_orders(), ())

        self.assertIs(tradingbot_router.trading_bot, original_trading_bot)
        self.assertEqual(
            tradingbot_router.trading_bot.list_paper_orders(),
            original_orders,
        )

    def test_root_responds_over_asgi(self):
        status, headers, body = call_asgi("GET", "/")

        content_types = [
            value.decode()
            for name, value in headers
            if name.decode().lower() == "content-type"
        ]

        self.assertEqual(status, 200)
        self.assertTrue(
            any(ct.startswith("application/json") for ct in content_types)
        )

        payload = json.loads(body)
        self.assertEqual(
            set(payload.keys()),
            {"system", "module", "environment", "status", "time"},
        )
        self.assertEqual(payload["system"], settings.app_name)
        self.assertEqual(payload["module"], "Core")
        self.assertEqual(payload["environment"], settings.environment)
        self.assertEqual(payload["status"], "online")
        self.assertIsInstance(payload["time"], str)
        # Raises if not a valid ISO 8601 timestamp; value itself is dynamic.
        datetime.fromisoformat(payload["time"])

    def test_modules_responds_over_asgi(self):
        status, headers, body = call_asgi("GET", "/modules")

        content_types = [
            value.decode()
            for name, value in headers
            if name.decode().lower() == "content-type"
        ]

        self.assertEqual(status, 200)
        self.assertTrue(
            any(ct.startswith("application/json") for ct in content_types)
        )

        payload = json.loads(body)
        self.assertEqual(set(payload.keys()), {"modules", "updated"})
        self.assertIsInstance(payload["updated"], str)
        datetime.fromisoformat(payload["updated"])

        modules = payload["modules"]
        self.assertEqual(set(modules.keys()), set(registry.modules.keys()))

        loaded = loader.loaded_modules
        self.assertIn("AI Assistant", loaded)
        self.assertIn("Trading Bot", loaded)

        self.assertEqual(modules["core"], registry.modules["core"])
        self.assertEqual(modules["home"], registry.modules["home"])
        self.assertEqual(
            modules["ai"],
            {
                **registry.modules["ai"],
                "status": loaded["AI Assistant"]["status"],
                "version": loaded["AI Assistant"]["version"],
            },
        )
        self.assertEqual(
            modules["trading"],
            {
                **registry.modules["trading"],
                "status": loaded["Trading Bot"]["status"],
                "version": loaded["Trading Bot"]["version"],
            },
        )


if __name__ == "__main__":
    unittest.main()
