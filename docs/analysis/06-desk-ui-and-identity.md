# 6. Desk UI and identity

Observed from source plus live monitor flags. This pass is contract and structure, not a restyle.

## Job

What the human sees, and which copy/controls the production monitor must not grow.

## Source of truth

- ASH: [`static/index.html`](../../static/index.html), [`docs/ui-rulebook.md`](../ui-rulebook.md), [`.cursor/skills/ash-*`](../../.cursor/skills/), `desk_configured`, `explain_now`, `session_clock`
- Live: `/api/status` `configured` true, `environment` production, skip-intro / monitor lock in release `4832132`

## Invariants

- One UI file. Reuse `resize()` and existing drawers. No Chart.js/D3 for a panel.
- Nothing readable below 11 px. Touch 44×44. Color is never the only cue. Live candles are ash/grey; green/red is an intro costume.
- Title engine and desk type/phone contract are shipped. Do not rebuild the A, 26-letter alphabet, or WebGL.
- Production / `/ash` / `?from=vault`: skip intro, hide Connect, `applyMonitorLock`.
- Visual work loads the rulebook and the matching ash-* skill. Do not restyle unless asked.

## How it works now

Home is the session explainer (clock + `explain_now`). Activity is the book (open/closed + comments). Lab is shadow, debrief, snapshots. Replay stays in the file, hidden from the dock.

`ASH_BASE` is true when `location.pathname === '/ash'`. `FROM_VAULT` is `?from=vault`. `SKIP_INTRO` is either. `api()` reads text then JSON so a 403 HTML/plain body does not look like a silent hang; `saveSetup` catch writes the error into the setup message.

`desk_configured()` makes production web `configured: true` without local keys. Connect fields hide under `applyMonitorLock`.

**Live:** configured true, process_role web, paper_only true. FamilyVault session URL is `/ash/?from=vault` (see [7](07-familyvault-front.md)).

## Tests and gaps

Covered in `test_safety`: vault path prefix (`ASH_BASE`, `ashUrl`, SW register), monitor lock / skip-intro strings, `api()` text parse, production desk without keys, security headers, no persistent cache on authenticated desk, guest cannot POST intro save, dashboard path prefix, journal HTML escape.

Not a visual regression suite. Playwright for the public desk lives in FamilyVault and hits `/ash` through Caddy, not canvas pixels.

## Drift, gaps, next question

- **Rulebook vs live monitor:** the rulebook describes a phone desk that can Connect. Production is a read-only monitor. The overlay copy says so; the rulebook does not yet name FamilyVault as the door.
- **STRATEGIES `plain` anecdotes** still read like a prior session (see [4](04-signals-and-models.md)).
- **Next question:** should Home grow a one-line “book vs Alpaca” chip (+503 closed vs +504 equity) without turning Activity into a broker blotter?

Points at: [7](07-familyvault-front.md), [8](08-security-and-monitor.md), [2](02-ledger-and-pnl.md).
