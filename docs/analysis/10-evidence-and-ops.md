# 10. Evidence and ops contract

Observed Friday 21 August 2026 evening. Session closed; after-hours ops are allowed.

## Job

How agents and operators are supposed to act, and what evidence counts.

## Source of truth

- Tests: [`tests/test_safety.py`](../../tests/test_safety.py) (59 cases on last local run)
- Agent: [`.cursor/rules/ash-desk.mdc`](../../.cursor/rules/ash-desk.mdc), [`.cursor/rules/ash-ui.mdc`](../../.cursor/rules/ash-ui.mdc), [`.cursor/skills/ash-desk/SKILL.md`](../../.cursor/skills/ash-desk/SKILL.md), ash-ui skill group
- Deploy/health: `GET /api/health`, `healthcheck.py`, runner watchdog
- This set: [`README.md`](README.md) evidence ladder

## Invariants

- Load ash-desk for session start, restart, reconcile, PDT, 0DTE, or guest LAN. Load ash-ui (then the group) for visual work. Do not restyle unless asked.
- Start web and runner as **two** processes. Never `pkill -f "python app.py"`.
- Development SQLite is `data/development/arena.db`. `data/arena.db` is unused legacy.
- Promote strategy/algorithm edits on `dev` anytime; do not push or merge to `main` weekday 09:25–16:10 ET.
- After changing reconcile, `option_contract`, `pdt_block`, or guest writes: `python -m unittest tests.test_safety -v`.
- Chat memory is the bottom of the ladder. Re-verify.

## How it works now

**Safety tests, by the category they mostly serve**

| Category | Tests (names shortened) |
|---|---|
| 1 Authority | broker fail-closed, dual interlocks, paper-only URL, web cannot arm/read keys, import does not start runner, production desk without keys |
| 2 Ledger | startup no flat-buy rebuild, recover only if held, matching exit close, UUID repair, qty-2 split, expire from UUID, missing round-trip, unexplained OPEN fails, unknown pnl omitted, overnight/expiry booking dates |
| 3 Session/risk | PDT flagged and unread, 0DTE next-day refused, daily cap, DNT opening vs overnight, loser does not cross ticker |
| 4 Signals | ORB held/poke/shallow/deep, Aug 19 replay, pending/skip_dnt reuse, one-lot no scale |
| 5 Tape | snapshot reuse, chart cache depth, health without heartbeat, IEX junk not DNT |
| 6 UI | vault path prefix, monitor lock strings, headers, no persistent cache, journal escape |
| 8 Security | production read-only behind proxy, export blocked, guest intro POST blocked, comments when unarmed |
| 7 Vault | not in this file — FamilyVault vitest + Playwright live |

`start_wsl.sh` starts web + runner, forces the runtime interlock **false**, and prints a LAN URL. Production `start` is systemd `ash.target`. Health 200 means heartbeat ≤ 90s.

**Live tonight:** health ok, heartbeat 9s, both ASH units active, deploy/backup timers active, book +503 closed / +504 equity, one OPEN QQQ weekly put. After-hours runner restart was already used for the matcher; do not treat that as a template for Monday 09:35.

## Tests and gaps

The safety file is the executable contract for ASH. It does not start a runner loop. It does not talk to live Alpaca. It does not render the phone.

FamilyVault live Playwright is the executable contract for the public door. ASH loopback Playwright needs an IAP tunnel (`18765:127.0.0.1:8765`).

No test encodes “do not bounce in ORB.” That lives in the skill and the deploy deferral.

## Drift, gaps, next question

- **This analysis set** is source + one live pass. Monday’s open will change clock, PDT, and fires. Re-run categories 2–5 after the first window, not from this file’s evening numbers alone.
- **Runner arming vs git unit** is the ops item most likely to surprise (see [1](01-process-and-authority.md) and [9](09-deploy-backup-recovery.md)).
- **Next question:** do you want these writeups committed, or kept as working notes until the next after-hours promote?

Points at: every other category. This file does not own product behavior; it owns how we are allowed to touch it.
