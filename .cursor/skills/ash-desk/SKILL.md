---
name: ash-desk
description: >-
  ASH Terminal paper-desk operations. Start or stop the WSL session, web, and
  runner; check health; reconcile Activity vs Alpaca; 0DTE same-day, PDT, guest
  LAN. Use when the user says start a session, 9:30, runner, health, reconcile,
  paper orders, PDT, 0DTE, Activity ledger, or start_wsl.sh.
---

# ASH desk

Paper scanner on a phone-first Flask desk. Cinema is the door; this skill is the session. Load on ops. Do not restyle.

## Env and processes

- `CEG_ENV=development`. Config is gitignored `config.development.json` (copy keys from `config.json` if missing; never commit it).
- Orders stay off unless **both** `broker_orders_enabled` is the JSON literal `true` and `CEG_ALLOW_BROKER_ORDERS=true`. [`start_wsl.sh`](../../../start_wsl.sh) forces the runtime interlock **false**.
- Start **web** (`app.py`) and **runner** ([`runner.py`](../../../runner.py)) as two processes. Importing `app.py` never scans. Kill by PID, not `pkill -f "python app.py"`.
- Live book: `data/development/arena.db`. `data/arena.db` is unused legacy. If development is missing and legacy exists, seed by copy once — do not auto-merge mid-session.

## After start

1. `GET /api/health` → HTTP 200 (runner heartbeat ≤ 90s). 503 means Flask is up and the runner is not.
2. Open Activity. Rows must keep `trade_date` / fill times. Ghost `EXPIRED` at full debit after a restart means buys were replayed; stop and fix the book, do not keep scanning.
3. Same env on both processes: `CEG_ENV=development` and the orders interlock you intend.

## Clock (America/New_York)

From `session_clock()` in [`app.py`](../../../app.py):

| id | window |
|---|---|
| OPN | 09:35–09:55 |
| OSF | 09:50–10:25 |
| ORB | 10:05–11:30 |
| VRC | 10:30–13:00 |
| MVR | 11:00–14:30 |
| EOD | 15:45–15:49 |
| EXIT | 15:50–16:05 |

Do not bounce the runner inside those windows unless the user asked.

## Fail closed

- **0DTE:** same calendar expiry only. No next-week fallback. Missing contract → `SKIP_NO_0DTE`, not a fill (`option_contract` / `submit_entry`).
- **PDT:** EOD blocked under $25k if `pattern_day_trader` or `daytrade_count >= 3`, or if the account call fails. Overnight may still send.
- **Reconcile:** Activity is the book. Recover a buy as OPEN only if Alpaca still holds that symbol. Do not insert closed history from buy-side replay.
- **Guest LAN:** phone GET of Home/Activity is allowed. Mutating `/api/*` is local-only (`_guest_lan`). Keep bind `0.0.0.0` so the phone loads; optional `CEG_BIND`.

## Tests

After changing reconcile, `option_contract`, `pdt_block`, or guest writes, run:

```bash
python -m unittest tests.test_safety -v
```

## After the close

Rename leftover `data/arena.db` (e.g. `data/arena.legacy-YYYYMMDD.db`). Do not delete it. Do not merge ledgers while RTH is open.

## Promote to main

`dev` is daytime work. `main` is after-hours promote only.

- After 16:10 ET: merge/push `main`, let `ash-deploy.timer` + 16:15 runner upgrade apply it.
- Do not bounce a live runner to get the new sleeve in during OPN/OSF/ORB/VRC/MVR/15:45.
- Do not push or merge to `main` on a weekday 09:25–16:10 America/New_York.
