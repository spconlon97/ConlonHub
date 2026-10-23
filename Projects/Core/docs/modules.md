# Conlon Hub Core — Module Reference

Baseline: 2026-10-20, commit `a01042b` (`feature/marvis-tool-orchestration`).

Evidence key: **[code]** read in source · **[test]** covered by the passing suite
(323 OK, 2026-10-20) · **[README]** stated in README, not separately verified ·
**[runtime]** observed on the host · **[unverified]** not checked.

All database paths are relative to the repository root (`Databases/`), not
`Projects/Core`.

## Core (`app/main.py`, `app/core/`)

- **Purpose:** assembles the FastAPI app, includes the `tradingbot`, `ai`, `phone`
  and `auth` routers, and serves `GET /`, `GET /modules`, `GET /loaded-modules`.
  [code]
- **Entry point:** `python -m uvicorn app.main:app`, or `scripts\start_marvis.ps1`.
  [README]
- **Submodules:**
  - `config.py` — pydantic-settings `Settings`, reads `.env`. [code]
  - `registry.py` — static module list for `GET /modules`. [code]
  - `auth/` — bearer credentials, `bootstrap` and `revoke` CLIs,
    `GET /auth/whoami`, security audit log. [code][test]
  - `capabilities/` — registry of read-only capabilities (system modules,
    trading status, paper account, paper orders) used by MARVIS tool
    orchestration. [code]
  - `database/migrations.py` — SQLite migrations. [code]
- **Module system:** `app/modules/base.py` (`ModuleBase` with `start()` /
  `status()`) and `app/modules/loader.py` (instantiates `AIAssistant` and
  `TradingBot` lazily on first request). [code]
- **Data owned:** `Databases/core_auth.db`, `Databases/core_audit.db`. [code]
- **Configuration (names only):** `APP_NAME`, `ENVIRONMENT`, `VERSION`,
  `AI_HISTORY_MESSAGE_LIMIT` (2–200, even), `AI_REQUESTS_PER_MINUTE` (1–120).
  [code]
- **Startup/shutdown:** no lifespan or startup/shutdown hooks are defined. [code]
  Stop with Ctrl+C or by ending the launcher process. [unverified]

## MARVIS AI Assistant (`app/modules/ai/`)

- **Purpose:** authenticated chat assistant with stored conversations.
- **Endpoints:** `GET /ai/status`, `POST /ai/respond` (auth required),
  `GET /ai/conversations`, `GET /ai/conversations/{id}`,
  `DELETE /ai/conversations/{id}`. [code][test]
- **Tool use:** bounded, read-only tool orchestration (`orchestration.py`) over
  the Core capability registry. [code][test]
- **Phone chat:** `GET /phone`, `GET /phone/api/status`, `POST /phone/api/respond`;
  requires Tailscale Serve identity headers and a connection from the local
  proxy. [README][test]
- **Providers:**
  - Ollama at `http://127.0.0.1:11434/api/chat`, default `qwen3.5:9b`. [code]
    Ollama 0.40.6 running with `qwen3.5:9b` (Q4_K_M) installed. [runtime]
  - OpenAI (optional), default `gpt-5.6-luna`. [code]
  - LM Studio is not used by the code. [code]
- **Configuration (names only):** `AI_PROVIDER`, `OLLAMA_MODEL`,
  `OLLAMA_ENDPOINT`, `OPENAI_API_KEY` (secret — the launcher decrypts a DPAPI
  file into the process environment only), `OPENAI_MODEL`. [code]
- **Data owned:** `Databases/core_ai.db`, isolated per principal. [code]
- **Limits:** prompts capped at 16,000 characters; per-principal rate limit;
  history sent to OpenAI is capped. [README][test]

## TradingBot — paper only (`app/modules/tradingbot/`)

- **Purpose:** simulated paper trading; never places real orders.
- **Endpoints:** `POST /tradingbot/paper-orders`, `GET /tradingbot/paper-orders`,
  `GET /tradingbot/paper-account`, `POST /tradingbot/paper-portfolio`,
  `POST /tradingbot/paper-pnl`. [code][test]
- **Safeguards:**
  - `live_trading_enabled` defaults to `False`; `True` raises
    `ValueError("Live trading is disabled.")`. [code]
  - Max order value `1000.00`; starting cash `10000.00`. [code][test]
  - No network imports in the module; prices are caller-supplied only. [code]
  - Rejected orders are not stored. [README][test]
- **Data owned:** `Databases/paper_orders.db`. [code]
- **Authentication:** every `/tradingbot/*` route requires the Core bearer
  credential via a router-level `Depends(require_principal)`; routes added to
  this router inherit it. [code][test] There is still a single shared paper
  account, not one per principal.

## Scripts (`scripts/`)

- `start_marvis.ps1` (`-Provider`, `-Model`, `-Reload`), `start_marvis_hidden.py`,
  `setup_marvis_access.ps1`, `chat_marvis.ps1`, `store_openai_key.ps1`. [README]
  Script contents not reviewed. [unverified]

## Verification

From `Projects\Core`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

2026-10-20: 323 tests OK. Output includes five
"Security audit event could not be persisted." lines, likely from tests that
exercise that failure path. [unverified] `Databases/` file hashes were unchanged
by the run.
