# Git / Repository Structure

- This project (`Projects/Core`) is **not its own git repo** — it is a subdirectory
  of the larger `ConlonHub` monorepo. Current checkout:
  `C:\Users\seanpaul\Documents\ConlonHub`.
  Remote: `origin` → `https://github.com/spconlon97/ConlonHub.git`.
- A separate repo, `spconlon97/conlon-hub` (lowercase, YouTube/content backend,
  `marvis/project-control-phase8`), is an unrelated codebase with no shared history.
- A sibling directory `Projects/TradingBot` has been referenced but is **not present**
  in this checkout (2026-10-20). If it appears, it is a separate project tree from
  `app/modules/tradingbot` inside Core.
- Root `.gitignore` ignores: `**/.venv/`, `**/__pycache__/`, `*.pyc`/`*.pyo`/`*.pyd`,
  `**/.env`, `Backups/`, `*.db`/`*.db-shm`/`*.db-wal`/`*.sqlite`/`*.sqlite3`, and
  Core tool artifacts (`.serena/logs/`, `.serena/project.yml.bak`,
  `.serena/project.yml.broken-*`, `.serena-backup-*/`, `.playwright-mcp/`).
  The `.serena/memories/` files are tracked.
- Branching convention: short-lived `feature/*` and `fix/*` branches (earlier
  `tradingbot-*`, now `marvis-*`) merged into `master` via GitHub PRs. History is
  small, single-purpose commits with conventional prefixes
  (`feat(core):`, `feat(ai):`, `fix(tradingbot):`, `docs(core):`).
- As of 2026-10-20, local `master` matches `origin/master`; active work is on
  `feature/marvis-tool-orchestration`.
