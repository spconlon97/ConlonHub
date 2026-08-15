# Code Style & Conventions

- **No type hints** are used in the application code seen so far (`main.py`,
  `registry.py`, `loader.py`, `base.py`, `config.py`) — function signatures and
  returns are untyped. Pydantic models (`Settings`, request bodies like
  `PaperOrderRequest`) get their typing from pydantic field declarations instead.
- **No docstrings** anywhere in the inspected modules — the code favors small,
  self-descriptive functions/classes over comments or docstrings.
- **Settings via pydantic-settings**: a single `Settings(BaseSettings)` class per
  concern (global in `app/core/config.py`, module-specific e.g. TradingBot's own
  `app/modules/tradingbot/config.py`), instantiated once as a module-level singleton
  (`settings = Settings()`), reading from a `.env` file.
- **Module system uses ABCs**: `app.modules.base.ModuleBase` (from `abc.ABC`) defines
  the contract (`start`, `status` as `@abstractmethod`) that concrete modules
  (`AIAssistant`, `TradingBot`) implement.
- **FastAPI routers per module**: TradingBot exposes its endpoints via its own
  `APIRouter` in `router.py`, included into the main `app` with `app.include_router(...)`
  rather than defining routes directly on `app` (except the 3 core routes in
  `main.py` itself).
- **Persistence is hand-rolled**, not an ORM: `sqlite_repository.py` talks to SQLite
  directly rather than via SQLAlchemy or similar.
- **Blank-line spacing**: files consistently use double blank lines between
  top-level imports/definitions (PEP 8 style), e.g. in `main.py` and `registry.py`.
- **Naming**: snake_case for functions/variables/files, PascalCase for classes
  (`ModuleBase`, `AIAssistant`, `TradingBot`, `PaperOrderRequest`), module-level
  singletons lowercase (`app`, `settings`, `router`).
