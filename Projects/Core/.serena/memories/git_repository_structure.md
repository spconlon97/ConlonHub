# Git / Repository Structure

- This project (`Projects/Core`) is **not its own git repo** — it is a subdirectory
  of the larger `ConlonHub` monorepo. Git root: `D:\ConlonHub`.
  Remote: `origin` → `https://github.com/spconlon97/ConlonHub.git`.
- A sibling directory `Projects/TradingBot` also exists in the monorepo — it is a
  **separate, unrelated project tree** from `app/modules/tradingbot` inside Core.
  Don't conflate the two when reasoning about "TradingBot".
- Root `.gitignore` (at `D:\ConlonHub\.gitignore`) ignores: `**/.venv/`,
  `**/__pycache__/`, `*.pyc`/`*.pyo`/`*.pyd`, `**/.env`, `Backups/`, and
  `*.db`/`*.db-shm`/`*.db-wal`/`*.sqlite`/`*.sqlite3`. Notably it does **not** cover
  `.venv-windows/`, `.serena/`, `.serena-backup-*/`, or `.playwright-mcp/` — these
  show up as untracked in `git status` inside Core.
- Branching convention observed (both local and on `origin`): short-lived
  `feature/tradingbot-*` and `fix/tradingbot-*` branches merged into `master`, plus a
  `chore/core-reproducibility` branch. Recent `master` history is a sequence of small,
  single-purpose commits (e.g. "Add simulated paper profit and loss calculator",
  "Expose simulated paper portfolio valuation") — prefer small, incremental commits
  matching this style.
- As of the last check, local `master` was ahead of `origin/master` by 1 unpushed
  commit.
