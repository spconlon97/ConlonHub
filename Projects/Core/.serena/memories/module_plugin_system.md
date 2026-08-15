# Module / Plugin Structure & Current Known Modules

**Pattern:** Modules are plain Python classes deriving from the ABC
`app.modules.base.ModuleBase`, which requires implementing `start()` and `status()`.
Each module also carries class attributes `name` (default `"Unnamed Module"`) and
`version` (default `"0.1.0"`), overridden per module.

`app/modules/loader.py` hard-codes the list of active module instances (not
auto-discovered):
```python
modules = [AIAssistant(), TradingBot()]
```
It populates a module-level `loaded_modules` dict lazily the first time
`get_loaded_modules()` is called, keyed by `module.name`, each entry containing
`name`, `version`, `status()`.

Separately, `app/core/registry.py` holds a **static**, hand-maintained dict
(`get_modules()`) describing modules for the `/modules` endpoint — this is metadata
only and is NOT wired to the loader/ModuleBase system. It currently lists:
- `core` — "Core", status `online`, v0.1.0
- `ai` — "AI Assistant", status `planned`, v0.1.0
- `trading` — "Trading Bot", status `planned`, v0.1.0
- `home` — "Home Automation", status `planned`, v0.1.0

Note the `/modules` registry says AI/Trading/Home are "planned" while
`/loaded-modules` actually instantiates real `AIAssistant`/`TradingBot` classes —
these two views can disagree and aren't kept in sync automatically.

**Current real modules under `app/modules/`:**
- `ai/assistant.py` — `AIAssistant`, minimal/placeholder implementation of
  `ModuleBase`
- `tradingbot/` — the fully built-out module:
  - `router.py` — FastAPI `APIRouter` (`tradingbot_router`), endpoints:
    `POST /tradingbot/paper-orders`, `GET /tradingbot/paper-orders`,
    `GET /tradingbot/paper-account`, `POST /tradingbot/paper-portfolio`; request
    models `PaperOrderRequest`, `PaperPortfolioRequest`
  - `trading_bot.py` — `TradingBot(ModuleBase)` module class itself
  - `config.py` — TradingBot-specific settings (e.g. paper order value limit)
  - `models.py` — data models (e.g. order representation)
  - `paper_broker.py` — paper-trading order execution logic (buy/sell validation)
  - `paper_account.py` — simulated cash balance & positions
  - `paper_portfolio.py` — caller-priced portfolio valuation
  - `paper_pnl.py` — simulated paper profit & loss calculation
  - `sqlite_repository.py` — hand-rolled SQLite persistence for paper orders
    (DB file at `Databases/paper_orders.db`, gitignored)
