# Project Overview — Conlon Hub Core

**Purpose:** Conlon Hub Core is a modular FastAPI application acting as a hub/host for
independent "modules" (mini-services). It currently hosts the Core service itself, an
AI Assistant module (placeholder/planned), and a safety-restricted, paper-only
TradingBot module.

**Tech stack:**
- Python 3 (compiled `__pycache__` shows both cpython-313 and cpython-312 — targets
  Python 3.12/3.13)
- FastAPI 0.141.1 (web framework)
- Pydantic 2.13.4 / pydantic-settings 2.15.0 (settings & request/response models)
- Uvicorn 0.52.1 (ASGI server)
- SQLite (via a hand-rolled repository, not an ORM) for TradingBot paper-order
  persistence
- `unittest` (stdlib) for tests — no pytest despite a stray `.pytest_cache/` present

**Repository context:** This project lives at `Projects/Core` inside the larger
`ConlonHub` monorepo (git root is `D:\ConlonHub`, remote
`https://github.com/spconlon97/ConlonHub.git`). A sibling project `Projects/TradingBot`
also exists in the monorepo but is a separate, unrelated tree — do not confuse it with
`app/modules/tradingbot` inside Core.

**Safety model (important, per README):** TradingBot is paper-trading only —
live trading, exchange connections, and API credentials are explicitly not supported.
Paper orders are capped in value, buys can't exceed virtual cash, sells can't exceed
held simulated positions, and portfolio valuation only ever uses caller-supplied
simulated prices (no live market data).
