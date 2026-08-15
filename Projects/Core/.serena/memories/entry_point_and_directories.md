# Entry Point & Important Directories

**Main FastAPI entry point:** `app/main.py`
- Creates `app = FastAPI(title=settings.app_name, version=settings.version)`
- Includes `tradingbot_router` from `app.modules.tradingbot.router`
- Defines top-level routes: `GET /` (health/home), `GET /modules` (static module
  registry via `app.core.registry.get_modules`), `GET /loaded-modules` (dynamically
  instantiated modules via `app.modules.loader.get_loaded_modules`)
- No FastAPI `lifespan`/`on_event` startup or shutdown handlers are defined anywhere
  in the app as of this writing.
- Run with: `python -m uvicorn app.main:app --reload`

**Important directories:**
- `app/` — application package root
  - `app/main.py` — FastAPI entry point (see above)
  - `app/config.py` — (top-level config file; distinct from `app/core/config.py`)
  - `app/database.py` — database helper(s)
  - `app/core/` — cross-cutting core code
    - `app/core/config.py` — `Settings(BaseSettings)` (pydantic-settings), reads
      `.env`; exposes `app_name`, `environment`, `version`
    - `app/core/registry.py` — static dict of known modules (`core`, `ai`, `trading`,
      `home`) with name/status/version, exposed via `get_modules()`
  - `app/modules/` — the plugin/module system (see `module_plugin_system` memory)
    - `app/modules/base.py` — `ModuleBase` ABC that all modules implement
    - `app/modules/loader.py` — instantiates modules and exposes
      `get_loaded_modules()`
    - `app/modules/ai/` — AI Assistant module (`assistant.py`)
    - `app/modules/tradingbot/` — TradingBot module (see below)
- `tests/` — `unittest`-based test suite (see `suggested_commands` memory)
- `requirements.txt` — pinned dependencies (fastapi, pydantic, pydantic-settings,
  uvicorn)
- `README.md` — setup, run, and API usage instructions (source of truth for commands)
- `Databases/paper_orders.db` — SQLite DB created at runtime by TradingBot,
  gitignored, not checked in
- `.venv` / `.venv-windows` — local virtual environments (gitignored, except
  `.venv-windows` is NOT actually covered by the repo's `.gitignore`, which only
  ignores `**/.venv/`, `**/__pycache__/`, `*.pyc`, `*.pyo`, `*.pyd`, `**/.env`,
  `Backups/`, and various `*.db*`/`*.sqlite*` patterns)
