# Module / Plugin Structure & Current Known Modules

**Pattern:** Modules are plain Python classes deriving from the ABC
`app.modules.base.ModuleBase`, which requires implementing `start()` and `status()`.
Each module also carries class attributes `name` (default `"Unnamed Module"`) and
`version` (default `"0.1.0"`), overridden per module.

`app/modules/loader.py` hard-codes the module classes (not auto-discovered):
```python
def _module_classes():
    return [AIAssistant, TradingBot]
```
Instances load lazily on first use (`get_loaded_modules()` / `get_module_instance()`),
keyed by `module.name`. A router can supply its own configured instance via
`register_module_instance()` — TradingBot's router does this so the API and the
loader share one authoritative instance.

`app/core/registry.py` holds a static dict for `/modules` (`core`, `ai`, `trading`,
`home`, defaulting to `planned`). `get_modules()` reconciles it with the loader: any
entry whose module is loaded reports the live status and version. `home` has no
module and stays `planned`.

**Current real modules under `app/modules/`:**
- `ai/` — MARVIS AI Assistant: `assistant.py` (module class), `providers.py`
  (Ollama / OpenAI), `orchestration.py` (bounded read-only tool use over the
  capability registry), `repository.py` (SQLite conversations, `core_ai.db`),
  `router.py` (`/ai/*`), `phone.py` (`/phone`, Tailscale Serve identity required)
- `tradingbot/` — paper-only trading:
  - `router.py` — `APIRouter` with router-level `Depends(require_principal)`;
    `POST`/`GET /tradingbot/paper-orders`, `GET /tradingbot/paper-account`,
    `POST /tradingbot/paper-portfolio`, `POST /tradingbot/paper-pnl`
  - `trading_bot.py` — `TradingBot(ModuleBase)`
  - `config.py` — `live_trading_enabled=False` (True raises), order value limit,
    starting cash
  - `models.py`, `paper_broker.py`, `paper_account.py`, `paper_portfolio.py`,
    `paper_pnl.py`
  - `sqlite_repository.py` — SQLite persistence (`Databases/paper_orders.db` at the
    repository root, gitignored)

**Capabilities** (`app/core/capabilities/`) expose module data to MARVIS as READ-only
capabilities and call module instances in-process, not over HTTP. Full reference:
`docs/modules.md`.
