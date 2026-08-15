# CLAUDE.md — Conlon Hub Core

Operating rules for Claude Code sessions working in this project.

## Project scope

- This file applies to `D:\ConlonHub\Projects\Core`.
- The Git repository root is `D:\ConlonHub` (Core is a subdirectory of that monorepo,
  not its own repo).
- `D:\ConlonHub\Projects\TradingBot` is a separate sibling project. Do not inspect,
  modify, stage, commit, move, or delete anything in it unless explicitly requested.
  It is unrelated to the `app/modules/tradingbot` module inside Core.

## Context and token efficiency

- Use Serena memories first when starting work in this project.
- Use Serena symbolic tools (symbol overview, find symbol, find references) before
  reading whole files.
- Avoid recursively reading the whole repository.
- Read only the files or code regions required for the current task.
- Reuse existing project knowledge (Serena memories) instead of rediscovering the
  architecture every session.

## Current documentation

- Use Context7 when behavior depends on current third-party library/framework
  documentation (e.g. FastAPI, Pydantic, Uvicorn behavior or APIs).
- Prefer current official/library documentation over assumptions from model memory.
- Do not use Context7 unnecessarily for stable project-local facts already captured
  in Serena memories or directly readable from this codebase.

## Browser/UI verification

- Use Playwright for browser-based verification, frontend behavior, and UI flows
  when useful.
- Prefer isolated Playwright sessions.
- Close browser sessions when finished.
- Do not use browser automation when code/unit tests are sufficient.

## Safety

- Inspect `git status` before substantive work.
- Never delete, overwrite, or move unknown/untracked files simply to make Git clean.
- Never run destructive Git commands (`git reset --hard`, `git clean -fd`, force
  push, destructive checkout) unless explicitly instructed.
- Do not commit or push unless explicitly requested.
- Do not change secrets, credentials, `.env`, authentication configuration, or MCP
  credentials unless explicitly requested.
- Do not expose credentials or tokens in output.
- Preserve the existing paper-trading-only safety restrictions of the TradingBot
  module (no live trading, no exchange connections/credentials, order value limits,
  cash/position limits, caller-supplied prices only).

## Development workflow

- Understand existing architecture before modifying code.
- Prefer small, focused changes rather than broad rewrites.
- Preserve existing public behavior unless the task explicitly requires a change.
- Follow existing coding style and conventions.
- Add or update tests when behavior changes.
- Run the narrowest relevant tests first, then broader regression tests when
  appropriate.
- Do not install or upgrade dependencies merely because newer versions exist.

## Verification

- Distinguish between inspection, implementation, and verification.
- Do not claim something works unless it has actually been checked.
- Report tests/tools actually run and their results.
- Report warnings, skipped tests, and limitations explicitly.

## Tool preference

1. Serena — for understanding/navigating project code.
2. Normal targeted file reads — when Serena is insufficient.
3. Context7 — for current library/framework docs.
4. Playwright — for browser/UI verification.
5. Shell commands — only when needed for inspection, tests, or explicitly requested
   work.
