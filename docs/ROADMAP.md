# Conlon Hub Roadmap

> **Status: adopted 2026-11-15.** "Built" = verified in this repo; everything
> else is a plan, and each phase still gets its own design review before code.
> The owner decisions at the end remain open. Update this file as decisions are
> made; it replaces chat history as the source of truth for *what* we build and
> in *which order*.

## What Conlon Hub is

A private, local-first platform on the home PC (RTX 3060 12 GB, Windows 11),
with **MARVIS** as the assistant that can see into every part of it and,
with explicit human approval, act in it. Reached from the phone over a
private Tailscale network.

## Principles (apply to every phase)

1. **Local first.** Local models (Ollama, `qwen3.5:9b`) by default; cloud only
   with explicit opt-in per feature.
2. **Read freely, act only with approval.** New abilities start as READ
   capabilities. Anything that changes the world is an ACTION behind the
   approval gate (propose → human approves → runs at most once → audited).
3. **Paper / simulated before real.** Trading stays paper-only. Any real-world
   effect (money, devices, publishing, messages) needs its own owner decision
   recorded here first.
4. **One module at a time, tested.** Each module ships as a small PR with
   tests, docs in `docs/modules.md`, and a live check.
5. **Docs are the memory.** CLAUDE.md, `docs/modules.md`,
   `docs/TECHNOLOGY_REGISTER.md` and this roadmap, not chat logs.

## Built (verified)

| Area | State |
|---|---|
| Core platform | FastAPI app, module loader, migrations, bearer auth, audit log |
| MARVIS chat | Ollama `qwen3.5:9b`, stored conversations, rate limit, phone chat via Tailscale Serve |
| Tool use | READ capabilities: modules, trading status, paper account, paper orders. Tool requests are found anywhere in a model reply |
| Approval gates | Phases 3A–3D merged (PRs #6, #7, #8). MARVIS proposes; the owner approves on the phone card; the action runs at most once; outcome and audit recorded. False "order placed/approved" claims are replaced with a fixed message |
| First ACTION | `trading.place_paper_order`. **Live-tested on the phone 2026-11-15:** proposal created a pending request, Approve placed exactly one paper order (BTC-GBP 0.01 at 50000, cash 9500.00), audited |
| TradingBot | Paper-only orders, cash/positions, portfolio and P&L with caller-supplied prices; all routes authenticated |
| Tests | 438 `unittest` tests; real databases untouched by the suite |

## Phase 4: Harden the foundation (before any non-paper action)

- **Phone identity:** phone routes trust the `Tailscale-User-Login` header, so
  any local process calling `127.0.0.1:8000` could impersonate the phone user.
  Verify requests genuinely come through Tailscale Serve.
- **Remaining phone checks:** the chat "yes" pointer while a request is
  pending, and the over-cap refusal (both covered by automated tests; the
  approve path was live-tested 2026-11-15).
- **Backups:** scheduled copy of `Databases/` with a tested restore.
- **Health page:** one authenticated status view (service up, model loaded,
  last backup, pending approvals).

## Phase 5: Hub dashboard

A Conlon Hub home page (phone and PC): every module's status, MARVIS chat,
pending approvals, paper account summary. Mostly READ; reuses existing
endpoints. Makes each later module visible as soon as it lands.

## Phase 6+: Modules (order to be decided by the owner)

Each starts READ-only, then adds ACTIONs behind approval.

| Module | First READ slice | Later ACTIONs | Open questions |
|---|---|---|---|
| **Trading (XAU/USD strategy)** | Strategy signals and backtests on stored/simulated prices | Paper orders from signals (via approval) | Data source for prices; whether live trading is ever in scope (currently **no**) |
| **Home: energy** | Read meter/tariff data, daily usage summary | Scheduling devices | Which devices and integrations exist |
| **Home: CCTV & family dashboard** | Camera status, events list | Alerts, arming | Privacy rules, retention, which cameras |
| **Business reporting** | Daily business report (sales, stock, orders) | Drafted emails/tasks for approval | Which systems hold the data (website, wholesale) |
| **Business websites** | Site status and analytics | Content changes via approval | Hosting and deploy method |
| **Media / video** | Project and asset tracker | Render jobs; publishing only via approval | Relationship to the separate `conlon-hub` YouTube repo |
| **Long-term memory** | Decisions and provenance log MARVIS can read | — | Overlap with Serena memories and codebase-memory (see register) |

## Decisions needed from the owner

1. Order of Phase 6 modules (suggest: the one that saves the most time each week first).
2. Whether the YouTube `conlon-hub` repo ever merges into this hub.
3. Live trading: stays out of scope unless explicitly decided, after months of paper records.
4. Hardware facts to verify: system RAM and WSL2 (stated in chats, not yet checked).
