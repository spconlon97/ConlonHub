# Suggested Commands (Windows / PowerShell)

**Setup:**
```powershell
cd Projects\Core
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```
(Note: an alternate `.venv-windows` venv also exists in this checkout alongside the
usual `.venv`.)

**Run the app (dev, auto-reload):**
```powershell
python -m uvicorn app.main:app --reload
```
Key local URLs once running:
- http://127.0.0.1:8000/
- http://127.0.0.1:8000/loaded-modules
- http://127.0.0.1:8000/tradingbot/paper-orders
- http://127.0.0.1:8000/tradingbot/paper-account
- http://127.0.0.1:8000/docs  (Swagger UI)

**Run tests:**
```powershell
python -m unittest discover -s tests -v
```
The suite is `unittest`-based (not pytest, despite a stray `.pytest_cache/` in the
tree). As of this writing it contains 25 TradingBot safety tests across
`tests/test_paper_account.py`, `tests/test_paper_pnl.py`,
`tests/test_paper_portfolio.py`, `tests/test_tradingbot.py`,
`tests/test_tradingbot_account.py`.

**No separate lint/format command was found** (no ruff/black/flake8 config or
pre-commit hooks discovered in this project directory) — treat this as unconfirmed
absence rather than a strict rule; re-check if tooling is added later.

**Repo-root Windows utility commands** (this is a Windows box; prefer PowerShell
cmdlets over Unix tools when working outside the Bash tool):
`Get-ChildItem` (ls), `Set-Location` (cd), `Get-Content` (cat), `Select-String`
(grep), `Get-ChildItem -Recurse -Filter` (find). Inside the Bash tool (git-bash),
standard POSIX `ls`/`cat`/`git` work as shown in this memory.
