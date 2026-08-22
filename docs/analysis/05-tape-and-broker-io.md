# 5. Tape and broker I/O

Observed Friday 21 August 2026, 20:40 America/New_York.

## Job

What prices and account facts the desk believes, and what happens when the broker or tape is wrong.

## Source of truth

- ASH: `ingest_live_data`, `fetch_bars` / `fetch_bars_multi`, `live_bars`, `live_quotes`, `getj` / `getj_cached`, `api_log`, `api_cache`, `broker_account`, `live_or_stored_account`, `snapshot_account`, `clock_skew`, `bar_integrity`, `do_not_trade_reasons`
- Live: heartbeat, account snapshot timestamp, IEX feed in `test` and fetch helpers

## Invariants

- Market data URL is `https://data.alpaca.markets`. Broker URL is paper-only (see [1](01-process-and-authority.md)).
- Production web does not call `ah()`. It reads snapshots the runner wrote.
- Account snapshot is reused when the live account call fails (`test_account_snapshot_is_reused_when_broker_is_down`).
- Health is 503 if runner heartbeat is missing or older than 90s, even if Flask is up.
- IEX is not SIP. DNT ignores quote NBBO on purpose.

## How it works now

The runner, weekday 09:25–16:10, ingests live data and refreshes the daily cache. Minute history is filled before 09:35 and after 16:05, or kicked in the background during RTH. Every ~30s cycle also snapshots account and positions, reconciles, and submits due exits.

`getj_cached` uses in-process memory plus SQLite `api_cache`. `api_log` keeps the last 2500 calls. Web `market_chart` will not `ensure_daily_cache` or fetch when `WEB_READ_ONLY`.

`live_or_stored_account`: web always `stored_account()`. Runner tries live, writes snapshot, falls back to stored.

**Live:** heartbeat age 9s, health `ok` true, snapshot_at 20:40:19 ET, equity/cash as in [2](02-ledger-and-pnl.md). `watchdog_stale` false. `ash-runner` WatchdogSec=100 matches the 90s health window plus slack.

## Tests and gaps

Covered: snapshot reuse; daily chart cache depth; health without heartbeat; DNT vs IEX junk on OPN/ORB; bar-ish ORB fixtures.

Not covered: a live assertion that IEX coverage ≥90% for Monday’s open, or that `api_log` 429s page an operator. `clock_skew` exists in code; no safety test names it.

## Drift, gaps, next question

- **Gap:** `daytrade_count` / `pattern_day_trader` did not appear on the meta blob read tonight. PDT still reads live `broker_account()` on the runner, so the gate can be right while the monitor snapshot is thin.
- **Web charts** can go stale if the runner stops ingesting; Home should then fail health, not invent bars.
- **Next question:** is Monday’s open willing to fire on IEX + local bars at 22 prints (tests say yes for OPN), and do you want a coverage chip on Home when `session_pct < 0.9`?

Points at: [3](03-session-and-risk.md) (DNT), [6](06-desk-ui-and-identity.md) (what Home shows when tape is thin), [8](08-security-and-monitor.md) (web has no data keys).
