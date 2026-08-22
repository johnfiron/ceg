# 4. Signals and models

Observed Friday 21 August 2026 evening. No live fire (session closed).

## Job

Why the desk would enter, and how a signal becomes a ticket or a skip.

## Source of truth

- ASH: `STRATEGIES`, `strategy_signals`, `midday_signals`, `evaluate_and_trade` / `evaluate_midday`, `submit_entry`, `option_contract`, `strat_opt`, `thresh`, `ab_book`
- Replay: [`README.md`](../../README.md) (GREEN/RED/GRAY is next-open vs 3:45 underlying, not “signal fired”)
- Live: open id 45 is MACD QQQ PUT (overnight sleeve), not a midday 0DTE

## Invariants

- Fifteen models. Overnight (CEG, VCT, XED, LAR, RSI2, BB, MACD, DON, STO, KEL): 15:45, next-session 1% OTM weekly. Midday (OPN, OSF, ORB, VRC, MVR): session windows, ATM 0DTE, EOD horizon.
- Midday tickers are the ten names in `MIDDAY_TICKERS`. Overnight uses SPY/QQQ/IWM.
- Replay labels are a directional underlying proxy. Do not treat them as fill quality.
- Missing 0DTE contract → `SKIP_NO_0DTE`, not a next expiry.
- One open ticket per strategy+ticker. Opposite direction on the same ticker is `SKIP_OPPOSITE`.

## How it works now

`runner_loop` evaluates midday 09:35–14:30 and EOD 15:45–15:49. Signals are logged; `submit_entry` is what can buy.

Overnight examples: CEG wants RSI3<15, close position<30%, RVOL>1.2, VIX≥15, tomorrow macro-clear. RSI2 wants close above SMA200 and RSI2<10. BB/MACD/DON/STO/KEL are textbook two-sided.

Midday: OPN holds a ≥35 bp gap; OSF fades a gap already through prior close; ORB needs three 1-minute closes still outside the 09:30–10:00 box by ≥15 bp (not a poke); VRC rides a VWAP reclaim; MVR fades a VWAP stretch with 5-min RSI extreme.

`thresh()` defaults (overridable per book A/B): ORB break 15 bp, MVR stretch 1.25 ATR, OPN gap 35 bp, max 3 daily fires, quote max age 15s. Live production config does not override `max_daily_fires`.

If orders are disabled, `submit_entry` returns `SIGNAL_ONLY` and still records shadow/contract logs. Live web status says orders disabled; the runner interlocks are armed (see [1](01-process-and-authority.md)).

## Tests and gaps

Covered: ORB three held closes; poke miss; shallow vs deep hold; Aug 19 replay tape; OPN 22 bars + IEX junk is not DNT; ORB META IEX spread is not DNT; one-lot does not scale to flat; pending lock / skip_dnt reuse.

Not a model-validation suite: no walk-forward harness in `tests/` for the ten overnight rules. Lab/debrief and `strategy_journal` exist for after-hours judgment, not CI.

## Drift, gaps, next question

- **STRATEGIES `plain` text** still mentions old session anecdotes (“fired today”, “false thin-tape gate”). That is copy drift, not the live gate.
- **Open MACD QQQ** is an overnight weekly put through 24 Aug. It is the book’s only live expression tonight.
- **Next question:** which midday sleeves are allowed to fire Monday given PDT/account unread, and is `SIGNAL_ONLY` vs live send what you want with the runner interlock true?

Points at: [3](03-session-and-risk.md) (gates after the model), [6](06-desk-ui-and-identity.md) (explain box).
