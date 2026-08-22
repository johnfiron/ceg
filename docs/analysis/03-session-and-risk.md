# 3. Session clock and risk gates

Observed Friday 21 August 2026, 20:40 America/New_York.

## Job

When a ticket may exist, and which gates stop a fire that the model liked.

## Source of truth

- ASH: `session_clock`, `pdt_block`, `option_contract`, `submit_entry`, `do_not_trade_reasons`, `daily_fire_count`, `cluster_count`, `loser_cooldown`, `bp_block`, `thresh`, `submit_due_exits`
- Ops: [`.cursor/skills/ash-desk/SKILL.md`](../../.cursor/skills/ash-desk/SKILL.md)
- Live: `/api/status` clock, account snapshot equity / PDT fields

## Invariants

- Clock is America/New_York. Weekend = no scan.
- Live windows: OPN 09:35–09:55, OSF 09:50–10:25, ORB 10:05–11:30, VRC 10:30–13:00, MVR 11:00–14:30, EOD 15:45–15:49, EXIT 15:50–16:05. Do not bounce the runner inside those unless asked.
- Same-day 0DTE stays that calendar expiry. No next-week fallback while the sleeve is 0DTE.
- PDT: EOD blocked under $25k if `pattern_day_trader` or `daytrade_count >= 3`, or if the account call fails. Overnight may still send.
- Daily cap counts **open** risk (`ENTRY_SUBMITTED`/`OPEN`/`EXIT_SUBMITTED`), not scratches.
- DNT is hard blocks only: incomplete tape, thin session (except OPN/OSF), halt, earnings. IEX last/NBBO is ignored on purpose.

## How it works now

`session_clock` after 16:10 is `CLOSED`. Between windows on a weekday it is `WATCH`. Before 09:25 it is `PRE`.

`submit_entry` gate order (after open-dupe): opposite, daily cap, cluster, loser cooldown, PDT, contract, DNT, checklist/grade D, stale quote, buying-power, then `broker_orders_enabled`, then guest LAN.

`option_contract` for `dte=0dte` filters `expiration_date == td`. If the clock is ≥15:50 it advances `td` to the next session — that is the EXIT/after-close path, not a midday fallback.

`daily_fire_count` is per strategy per day on open statuses. Default `max_daily_fires` is 3. Live production config does not set `max_daily_fires` (None → code default 3). `contracts_per_trade` is 1.

**Live:** phase `CLOSED`, heartbeat 9s, equity $100,504.42 so PDT equity gate is not binding. Snapshot `daytrade_count` and `pattern_day_trader` were missing on the compact meta read used in this pass (`account_snapshots` columns exist; the meta blob used tonight did not surface them). `trading_blocked` was false. One OPEN overnight MACD QQQ put expiring 24 Aug — not a same-day 0DTE.

## Tests and gaps

Covered: PDT flagged EOD under $25k not overnight; PDT when account unread; 0DTE refuses next-day as 0DTE; daily cap counts open risk not scratches; DNT thin inside OPN/OSF skipped; DNT still blocks halt/earnings/incomplete tape; overnight still sees thin session; loser on QQQ does not block SPY; retryable skips include cap/stale/opposite not loser.

Not covered live: a weekday PDT probe against the real Alpaca `daytrade_count` field. Snapshot compactness can hide the flag the gate reads from `broker_account()`.

## Drift, gaps, next question

- **Gap:** monitor status does not show PDT block state. If the account call fails mid-session, EOD sleeves fail closed and Home may only show skips after the fact.
- **Clock vs promote:** weekday 09:25–16:10 is both the ingest/eval band and the “do not merge to main” band.
- **Next question:** persist `daytrade_count` / `pattern_day_trader` on every snapshot so the web can explain a PDT skip without calling Alpaca.

Points at: [4](04-signals-and-models.md) (who fires in each window), [5](05-tape-and-broker-io.md) (DNT tape), [1](01-process-and-authority.md) (orders still need interlocks).
