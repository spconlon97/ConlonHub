# Technology Register

KEEP / ADAPT / TEST / DISCARD decisions for external tools and ideas proposed for
MARVIS / Conlon Hub. A verdict is a recommendation, **not** approval to install.
Installation requires explicit user approval per item, a bounded test with
success criteria, and a rollback path.

- **KEEP** — useful and evidenced; retain (does not authorize installation).
- **ADAPT** — take the concept and fit it to MARVIS's existing design.
- **TEST** — bounded, reversible evaluation with success criteria and rollback.
- **DISCARD** — unsuitable or redundant for now; reason recorded.

Status column: **Installed** (present on the machine), **Not installed**, or
**Unknown source** (no repository identified; cannot be assessed).

## Assessed

### Superpowers — KEEP (installed, audited)

| Field | Detail |
|---|---|
| Source / date | `obra/superpowers` v6.4.2 (Jesse Vincent), MIT. Proposed in the Marvis Ideas Inbox (18 Sep 2026); installed 20 Oct 2026 through the Claude app plugin directory. |
| Provenance | The directory listing shows a partner review at commit `8ca22dba9a94f28898bbce59f2537ff4d87c747d`. On 20 Oct 2026 the installed files were compared with that commit and were **byte-identical** (ignoring `.git` and line endings). |
| Executable behaviour | A SessionStart hook (`hooks/session-start`, via Git Bash) reads its own `using-superpowers/SKILL.md` and injects it as session context; no network, no other commands. No MCP servers. Helper scripts run only when a skill invokes them and write to `.superpowers/sdd/` in the repo (self-gitignored). The optional brainstorming server binds `127.0.0.1` with a token, and its page loads a logo from `primeradiant.com`. |
| Fit | Planning, TDD, debugging and verification skills align with CLAUDE.md's development workflow. |
| Overlap / cost | Code-review and worktree skills overlap with Claude Code built-ins. The session-start text strongly pushes skill use on every task and adds context to every session; it defers to user instructions, so CLAUDE.md rules take precedence. |
| Rollback | Disable or uninstall in the Claude app plugin settings. Remove `.superpowers/` from the repo if created. |

### Playwright MCP (`microsoft/playwright-mcp`) — KEEP (not installed)
CLAUDE.md references Playwright for UI verification, but it is not configured.
Until approved, sessions use the built-in browser instead. Install only with
approval; rollback: remove the MCP server entry.

### GitHub MCP Server (`github/github-mcp-server`) — KEEP, low priority (not installed)
The remote is on GitHub, but the `gh` CLI already covers PRs and issues. Add only
if `gh` proves insufficient. Requires a GitHub token: review its scopes before connecting.

### NVIDIA SkillSpector — TEST (not installed)
Potentially useful for vetting third-party skills before enabling them. Run in an
isolated folder against a known skill first; verify the repository before use.

### Everything Claude Code (`affaan-m/ECC`), Agency Agents, Taste Skill, Book-to-Skill, Lord Claude (`aylee1024/lord-claude`) — TEST, one at a time, likely DISCARD as redundant (not installed)
Each adds skills or agents that overlap with Superpowers and the codebase-memory
agents, risking conflicting instructions and adding context to every session.
Only evaluate one at a time, against a specific gap Superpowers does not cover.

### Memanto (`moorcheh-ai/memanto`), AI Memory (`akitaonrails/ai-memory`) — DISCARD for now (not installed)
Memory is already covered by the Serena memory files and `codebase-memory-mcp`.
A third store would fragment project knowledge.

### Ruflo (`ruvnet/ruflo`), Fable Orchestrator, SuperPlane, OmniRoute — ADAPT (not installed)
MARVIS already has bounded tool orchestration and a capability registry, and
Phase 3 plans human approval gates. Borrow ideas, not a second agent framework.

### Awesome LLM Apps (`Shubhamsaboo/awesome-llm-apps`), DeepSeek Harness — Reference only
Nothing to install.

### n8n (`n8n-io/n8n`), Penpot MCP — Later (not installed)
n8n suits planned home/business automation; Penpot suits UI design work. Neither
module exists yet in Core.

### STRIX — Restricted TEST (not installed)
An offensive-security agent. If evaluated, run it only against the local MARVIS
instance (`127.0.0.1`), never against any other host.

### Unknown source
Taste Skill, Agency Agents, Book-to-Skill, Penpot MCP, OmniRoute, DeepSeek Harness,
Fable Orchestrator, SuperPlane and STRIX were listed only as "GitHub search".
Provenance cannot be assessed until an exact repository is identified.

## Open decisions (user)

- **Trading scope:** the Ideas Inbox describes "paper trading before live
  execution" for an XAU/USD bot; the MARVIS briefing states strictly paper-only.
  Core remains paper-only (`live_trading_enabled=False`, which raises if set to
  True) until the user decides otherwise.
- **Phase 3 approval gates:** proposed in the "Marvis build only 3060" chat
  (20 Sep 2026) as the prerequisite for any ACTION capability. ADAPT; not started.
