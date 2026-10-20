# Code Style & Conventions

- **Type hints are mixed:** the original modules (`main.py`, `registry.py`,
  `loader.py`, `base.py`, TradingBot `router.py`) are untyped, while newer code
  (`app/core/auth/`, `app/core/capabilities/`, `app/modules/ai/`) uses type hints
  on signatures and returns. Match the style of the file you are editing.
  Pydantic models get their typing from field declarations.
- **Docstrings are rare** (a handful of files); the code favors small,
  self-descriptive functions/classes, with comments reserved for non-obvious
  security or failure-handling reasoning (e.g. `app/core/auth/dependency.py`).
- **Settings via pydantic-settings**: a single `Settings(BaseSettings)` class per
  concern (global in `app/core/config.py`, module-specific e.g. TradingBot's own
  `app/modules/tradingbot/config.py`), instantiated once as a module-level singleton
  (`settings = Settings()`), reading from a `.env` file.
- **Module system uses ABCs**: `app.modules.base.ModuleBase` (from `abc.ABC`) defines
  the contract (`start`, `status` as `@abstractmethod`) that concrete modules
  (`AIAssistant`, `TradingBot`) implement.
- **FastAPI routers per module**: `tradingbot`, `ai`, `phone` and `auth` each expose
  an `APIRouter`, included into the main `app` with `app.include_router(...)`
  rather than defining routes directly on `app` (except the 3 core routes in
  `main.py` itself).
- **Auth via dependency**: protected routes use `Depends(require_principal)` from
  `app.core.auth.dependency` — per endpoint in `ai`/`auth`, router-level in
  `tradingbot`. Tests override it with `app.dependency_overrides`, scoped per test.
- **Persistence is hand-rolled**, not an ORM: `sqlite_repository.py` talks to SQLite
  directly rather than via SQLAlchemy or similar.
- **Blank-line spacing**: files consistently use double blank lines between
  top-level imports/definitions (PEP 8 style), e.g. in `main.py` and `registry.py`.
- **Naming**: snake_case for functions/variables/files, PascalCase for classes
  (`ModuleBase`, `AIAssistant`, `TradingBot`, `PaperOrderRequest`), module-level
  singletons lowercase (`app`, `settings`, `router`).
