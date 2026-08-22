# 2. Ledger and P&L truth

Observed Friday 21 August 2026, 20:40 America/New_York.

## Job

What is the book, how a fill becomes a row, and when P&L is confirmed versus guessed.

## Source of truth

- ASH: `trades` in [`app.py`](../../app.py) `init_db`, `submit_entry`, `submit_exit`, `_matching_exit_fill`, `_exit_remaining`, `expire_dead_options`, `startup_reconcile`, `option_pnl`, [`repair_ledger.py`](../../repair_ledger.py)
- FamilyVault: [`tradingLab.ts`](../../.familyvault-work/backend/src/routes/tradingLab.ts) `brokerBacked` / `guessedExpired` / `realized_pnl`
- Live: `/var/lib/ash/arena.db`, Alpaca paper fills (already attached 21 Aug)

## Invariants

- Activity is the book. Do not rebuild OPEN rows from historical Alpaca buys.
- Recover a filled buy as OPEN only if the broker still holds that symbol.
- Closed history is not inserted from buy-side replay unless an app-managed `x53-` sell proves the round trip (`allow_generic`).
- `option_pnl` uses local ticket qty vs the matched sell’s `filled_avg_price`, rounded to cents.
- Guessed `EXPIRED` is full debit and only after no remaining sell and the contract is not held.
- Two tickets may share one qty-2 `exit_order_id`. Remaining lots, not a consumed-id set.

## How it works now

Entry client ids are `a53-{YYYYMMDD}-{sid}-{ticker}`. App exits are `x53-{ticket}`. Alpaca 15:45 0DTE liquidations use UUID client ids. Matching order: exact `x53-{id}` / `exit_client_id`, then legacy `x53-{sid}-{ticker}-`, then (repair/expire only) same-symbol non-`x53` sells, then insert-only generic `x53-`.

`startup_reconcile` recovers held fills, closes OPEN-flat from a matched sell, expires only if worthless/EOD-due and still no sell, and fails closed if a live OPEN has no broker position and no explanation.

**Live book (45 trades)**

| Slice | n | P&L |
|---|---|---|
| OPEN | 1 (id 45 MACD QQQ `QQQ260824P00707000` qty 1) | mark, not booked |
| CLOSED BROKER | 1 | +20 |
| CLOSED BROKER_REPAIR | 24 | −356 |
| CLOSED SCHEDULE | 10 | +702 |
| CLOSED SIGNAL | 6 | +151 |
| CLOSED EXPIRED | 3 (ids 12/13/14 MVR AMZN/IWM/QQQ 17 Aug) | −14 |
| Closed total | 44 | **+503** |

Paper snapshot: equity $100,504.42 vs $100,000 start (+$504.42), cash $100,429.42, last_equity $99,978.10. The $1 gap is the open QQQ mark (~+$5 UPL) versus booked closed +503.

The 11 UUID liquidations were repaired 21 Aug (`ae1d2aac50fd572a`, backup `arena_pre-ledger-repair_20260821_194626.db`). A second dry-run was empty. 8/17 −$14 stays `EXPIRED` because Alpaca has no sell.

FamilyVault realized P&L sums only broker-backed closes. Guessed `EXPIRED` is reported separately (`unconfirmed_expired_*`). After the repair, those three 8/17 rows are the unconfirmed remainder.

## Tests and gaps

Covered: no rebuild from flat buys; recover only if held; UUID repair; qty-2 split vs 1-lot; expire-from-UUID not full debit; legacy x53 pairing; missing closed round-trip insert; unexplained OPEN fails startup; unknown `pnl` omitted from dashboard aggregates; overnight booked on NY exit date.

Not covered live: an automated ASH-vs-Alpaca fill diff in CI (repair is a CLI). Insert-from-buy still cannot attach a UUID sell by design.

## Drift, gaps, next question

- **Fixed this week:** UUID liquidations no longer become full-debit `EXPIRED` on expire/startup if a sell remains.
- **Remaining guessed book:** three 8/17 MVR tickets, −$14, no broker sell.
- **Next question:** should Trading Lab / Home label those three as “expired, no Alpaca sell” so they never look like the old −$1,091 ghost book?

Points at: [1](01-process-and-authority.md) (only runner writes), [3](03-session-and-risk.md) (when expire runs), [7](07-familyvault-front.md) (KPI split).
