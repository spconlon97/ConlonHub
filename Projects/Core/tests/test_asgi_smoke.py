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
from decimal import Decimal

from app.main import app
from app.modules import loader
from app.modules.tradingbot import router as tradingbot_router


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
            {"name": "AI Assistant", "version": "0.1.0", "status": "online"},
        )

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

    def test_paper_pnl_responds_over_asgi_using_authoritative_instance(self):
        account = tradingbot_router.trading_bot.account
        prices = {symbol: Decimal("1") for symbol in account.positions}
        payload = json.dumps(
            {"prices": {symbol: str(price) for symbol, price in prices.items()}}
        ).encode()

        status, headers, body = call_asgi(
            "POST",
            "/tradingbot/paper-pnl",
            body=payload,
            headers=[(b"content-type", b"application/json")],
        )

        expected_snapshot = tradingbot_router.trading_bot.paper_pnl_snapshot(prices)
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

    def test_paper_pnl_rejects_missing_price_over_asgi(self):
        payload = json.dumps({"prices": {}}).encode()

        status, headers, body = call_asgi(
            "POST",
            "/tradingbot/paper-pnl",
            body=payload,
            headers=[(b"content-type", b"application/json")],
        )

        with self.assertRaises(ValueError) as raised:
            tradingbot_router.trading_bot.paper_pnl_snapshot({})
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
        self.assertIn("Missing simulated price", expected_detail)
        self.assertEqual(json.loads(body), {"detail": expected_detail})

    def test_paper_portfolio_rejects_missing_price_over_asgi(self):
        payload = json.dumps({"prices": {}}).encode()

        status, headers, body = call_asgi(
            "POST",
            "/tradingbot/paper-portfolio",
            body=payload,
            headers=[(b"content-type", b"application/json")],
        )

        with self.assertRaises(ValueError) as raised:
            tradingbot_router.trading_bot.paper_portfolio_snapshot({})
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
        self.assertIn("Missing simulated price", expected_detail)
        self.assertEqual(json.loads(body), {"detail": expected_detail})


if __name__ == "__main__":
    unittest.main()
