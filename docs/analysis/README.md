# Desk analysis index

Method and map for understanding ASH + FamilyVault + the live paper host. Category writeups live next to this file. Do not treat chat memory as a finding until it is re-checked against the ladder below.

Observed: Friday 21 August 2026, evening America/New_York, after the regular session. Live host is GCE `familyvault` (`us-east1-c`). Paper only.

## Job

Understand how the desk actually works so later edits do not fight the book, the monitor boundary, or the session clock.

## Evidence ladder (highest first)

1. **Live observed** — systemd, `/opt/ash/current`, `/var/lib/ash/arena.db` queries, loopback `/api/health` and `/api/status`, FamilyVault Trading Lab JSON, Alpaca paper account/orders/positions. No keys, account ids, or JWTs in writeups.
2. **Executable tests** — [`tests/test_safety.py`](../../tests/test_safety.py), FamilyVault auth/session/Playwright, [`docs/security-verification-matrix.md`](../security-verification-matrix.md).
3. **Source** — [`app.py`](../../app.py), [`runner.py`](../../runner.py), [`static/index.html`](../../static/index.html), [`deploy/`](../../deploy/), FamilyVault BFF / `tradingLab`.
4. **Intent docs** — [`docs/ui-rulebook.md`](../ui-rulebook.md), [`docs/security_proto.md`](../security_proto.md), [`.cursor/skills/`](../../.cursor/skills/). When docs and source disagree, source and live win; record the drift.
5. **Chat memory** — lowest. Re-verify before it becomes a finding.

## Same pass for every category

- Job of this slice
- Source-of-truth files (ASH / FamilyVault / live path)
- Invariants (must not break)
- How it works now (code + live)
- Tests and what they do not cover
- Drift, gaps, and the next honest question

## Cross-cutting rules

Paper only. Web and runner are separate processes. Activity is the book. Same-day 0DTE stays same-day. PDT blocks EOD under $25k when flagged or daytrade count ≥ 3, or if the account cannot be read. Do not bounce the runner in OPN/OSF/ORB/VRC/MVR/15:45 unless asked. Weekday promote to `main` after 16:10 ET.

## Categories

Each category owns one question. Overlap is pointed at, not re-analyzed.

| # | Category | Owns | Writeup |
|---|---|---|---|
| 1 | Process and authority | Who may read, write, or order? | [01-process-and-authority.md](01-process-and-authority.md) |
| 2 | Ledger and P&L truth | What is the book? | [02-ledger-and-pnl.md](02-ledger-and-pnl.md) |
| 3 | Session clock and risk gates | When may a ticket exist? | [03-session-and-risk.md](03-session-and-risk.md) |
| 4 | Signals and models | Why would we enter? | [04-signals-and-models.md](04-signals-and-models.md) |
| 5 | Tape and broker I/O | What data is believed? | [05-tape-and-broker-io.md](05-tape-and-broker-io.md) |
| 6 | Desk UI and identity | What the human sees | [06-desk-ui-and-identity.md](06-desk-ui-and-identity.md) |
| 7 | FamilyVault front | How a browser reaches the desk | [07-familyvault-front.md](07-familyvault-front.md) |
| 8 | Security and monitor boundary | What must fail closed | [08-security-and-monitor.md](08-security-and-monitor.md) |
| 9 | Deploy, backup, recovery | How the machine stays honest | [09-deploy-backup-recovery.md](09-deploy-backup-recovery.md) |
| 10 | Evidence and ops contract | How agents and operators act | [10-evidence-and-ops.md](10-evidence-and-ops.md) |

Read **1 then 2** before the rest. Everything else hangs on who may act and what the book is.

## What this set is not

Not a restyle. Not identity research. Not a trading rewrite. Not a commit of secrets. Live numbers below are paper-account facts, not advice.
