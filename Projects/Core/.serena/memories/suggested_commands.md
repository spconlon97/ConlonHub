# Suggested Commands (Windows / PowerShell)

**Setup:**
```powershell
cd Projects\Core
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

**Run the app:**
- Normal operation: the `ConlonHub MARVIS` scheduled task runs
  `scripts\start_marvis_hidden.py` → `scripts\start_marvis.ps1` (Ollama
  `qwen3.5:9b`, `127.0.0.1:8000`, no reload). Restart it after code changes:
  `Stop-ScheduledTask "ConlonHub MARVIS"; Start-ScheduledTask "ConlonHub MARVIS"`.
  Runtime log: `%LOCALAPPDATA%\ConlonHub\logs\marvis-runtime.log`.
- Dev with reload (stop the scheduled task first to free port 8000):
  `.\scripts\start_marvis.ps1 -Reload`
- Chat from the terminal: `.\scripts\chat_marvis.ps1`

Key local URLs once running:
- http://127.0.0.1:8000/ , /loaded-modules , /ai/status — open
- http://127.0.0.1:8000/tradingbot/* , /ai/conversations — bearer credential required
- http://127.0.0.1:8000/docs (Swagger UI; use Authorize for protected routes)

**Run tests** (from `Projects\Core`):
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```
`unittest`-based. 325 tests as of 2026-10-20, covering TradingBot safety, auth,
AI providers/router/orchestration, capabilities, migrations, launcher, phone and
ASGI smoke tests. Five "Security audit event could not be persisted." lines are
expected: they come from tests exercising the audit-failure path.

**No lint/format tooling** is configured (no ruff/black/flake8/pre-commit config);
re-check if tooling is added later.

**Shell notes:** this is a Windows box; prefer PowerShell cmdlets outside the Bash
tool. Inside the Bash tool (Git Bash), POSIX `ls`/`cat`/`grep`/`git` work.
