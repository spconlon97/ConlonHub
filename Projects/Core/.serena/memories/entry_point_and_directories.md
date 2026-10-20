# Entry Point & Important Directories

**Main FastAPI entry point:** `app/main.py`
- Creates `app = FastAPI(title=settings.app_name, version=settings.version)`
- Includes four routers: `tradingbot` (`/tradingbot`), `ai` (`/ai`), `phone`
  (`/phone`, from `app.modules.ai.phone`) and `auth` (`/auth`)
- Defines top-level routes: `GET /` (health/home), `GET /modules` (static module
  registry via `app.core.registry.get_modules`), `GET /loaded-modules` (dynamically
  instantiated modules via `app.modules.loader.get_loaded_modules`)
- No FastAPI `lifespan`/`on_event` startup or shutdown handlers are defined anywhere
  in the app as of this writing.
- Run with: `python -m uvicorn app.main:app --reload`

**Important directories:**
- `app/` — application package root
  - `app/main.py` — FastAPI entry point (see above)
  - `app/core/` — cross-cutting core code
    - `app/core/config.py` — `Settings(BaseSettings)` (pydantic-settings), reads
      `.env`; exposes `app_name`, `environment`, `version`,
      `ai_history_message_limit`, `ai_requests_per_minute`
    - `app/core/registry.py` — static dict of known modules (`core`, `ai`, `trading`,
      `home`) with name/status/version, exposed via `get_modules()`
    - `app/core/auth/` — bearer credentials, bootstrap/revoke CLIs, `/auth/whoami`,
      audit log
    - `app/core/capabilities/` — read-only capability registry used by MARVIS tools
    - `app/core/database/migrations.py` — SQLite migrations
  - `app/modules/` — the plugin/module system (see `module_plugin_system` memory)
    - `app/modules/base.py` — `ModuleBase` ABC that all modules implement
    - `app/modules/loader.py` — instantiates modules and exposes
      `get_loaded_modules()`
    - `app/modules/ai/` — MARVIS AI Assistant (`assistant.py`, `providers.py`,
      `orchestration.py`, `repository.py`, `router.py`, `phone.py`)
    - `app/modules/tradingbot/` — TradingBot module (see below)
- `tests/` — `unittest`-based test suite (see `suggested_commands` memory)
- `requirements.txt` — pinned dependencies (fastapi, pydantic, pydantic-settings,
  uvicorn)
- `README.md` — setup, run, and API usage instructions (source of truth for commands)
- `docs/modules.md` — per-module reference with evidence markers
- `Databases/` at the repository root (not inside Core) — SQLite DBs created at
  runtime, gitignored: `paper_orders.db` (TradingBot), `core_ai.db` (AI),
  `core_auth.db` and `core_audit.db` (auth)
- `.venv` / `.venv-windows` — local virtual environments (gitignored, except
  `.venv-windows` is NOT actually covered by the repo's `.gitignore`, which only
  ignores `**/.venv/`, `**/__pycache__/`, `*.pyc`, `*.pyo`, `*.pyd`, `**/.env`,
  `Backups/`, and various `*.db*`/`*.sqlite*` patterns)
