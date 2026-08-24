# Current problems — before the 2026-08-24 open

Historical working list, not a restyle. The 2026-08-24 structural pass shipped the chart and hierarchy work on the local branch. FamilyVault GCP is **TERMINATED**. Do not add Chart.js / D3 / TradingView.

## Shipped in the whole-desk structural pass

- Charts: brush zoom, touch scrub, zoomed-window pan, FULL SESSION reset, visible-window Y scaling, dense-candle close trace, paired volume, compact ticker switching, and shared last-session identity.
- Home: session context → session total/account line → fixed equity path → closest setup → open sleeves/exits → evidence.
- Activity: only `CLOSED` records are closed fills; failed/incomplete entries are separate and missing quantity remains `NOT CAPTURED`.
- Models leads with strategy understanding and routes to Replay. Replay pairs price/volume and states Play/Pause/disabled transport.
- Lab exposes maturity/coverage/misses first and lazy-loads purpose-based research disclosures.
- Settings states explicit paper-order capability and organizes health, integrity, preferences, notifications, intro, and backups.
- Header/main landmarks, page headings, one Activity mark-seen path, decorative nav glyph handling, and pressed-state choice semantics are in place.

The detailed sections below preserve the original evidence. Items contradicted by the shipped list are resolved; remaining follow-up includes optional pinch/marker zoom and broader line-chart zoom reuse.

---

## 1. Charts — not a real tape tool yet

This is the reason the operator still leaves for Robinhood / TradingView. The inspect surface can load a session and print OHLC, but it does not let you **work the time**.

### 1.1 Interaction (must-have)

`bindChartInspect` only:

- mouse/pen **hover** to pick a bar
- **tap** to pick a bar (or hit an IN/OUT marker → Inspector)
- **← BAR / BAR →** and arrow keys

Missing, in this product’s material (not a drawing toolbar):

- **Drag a region on the plot to zoom into that time window.** Finger or mouse. Show the selected span on the readout while dragging. Clamp to bars that exist. Pair **volume** to the same window.
- **Pan** the zoomed window (drag on the already-zoomed tape, or two buttons).
- **Reset** to the full loaded session (one 44×44 control + Escape).
- **Touch scrub:** `pointermove` currently ignores `touch`, so a finger cannot drag along the tape the way a mouse can.
- **Pinch** is optional later; brush-zoom + reset + pan is the job.
- **Y follows X:** after a time zoom, rescale high/low to the visible bars so a 40¢ move is not a flat line in a $10 day range.
- **Double-tap / long-press** a fill marker should zoom around the entry, not only jump Inspector.

Keep 1m / 5m / DAILY as **resolution**, not as a substitute for zoom. Zooming 5m from 11:00–11:20 is the point.

### 1.2 The tape is hard to see

- Ash/grey candles on void are honest, but a full session on a 390px phone becomes **1px wicks** (`drawing.md`). 5m resample helps; a zoomed window should switch back toward 1m automatically when n is small enough for body width ≥ 3px.
- Live-audit measured ink on the bitmap, but the plot still **reads as a black rectangle** until you zoom or step. Last-price chip and axes are not enough contrast for the path itself (line weight on phone must stay ≥ 2px; consider a close-line behind thin candles when n is large).
- `startWait` can **wipe the canvas black** mid-refresh (`aria-busy`). A second `renderMulti` during `go('charts')` races the draw. The operator sees empty, then maybe candles.
- Volume under inspect is not inspectable (no shared crosshair, no zoom).

### 1.3 Weekend / last-session honesty

- `/api/live_bars/QQQ` for **today** is empty on Saturday/Monday pre-open. Inspect now falls back to **2026-08-21**, but **Live names** still says “No local bars yet.” Two stories on one page.
- Friday ingest **stopped ~12:37**. Open #12 recovered at **15:45**. The IN marker clamps to the last bar at 12:35. The chart cannot show the actual fill clock. Label that gap; do not invent bars.
- **Live names** should either hide on weekend, or list last-session names with the date chip — not a fake empty tape under a working inspect plot.
- DAILY / 1m / 5m do not share a selected window. Changing range throws away where you were.

### 1.4 Book vs chart

- Inspect list now keeps OPEN #12 and marked P&L. Closed QQQ on other days still **vanish** when `tradesForBars` requires `entry === last bar date`. Zooming into Friday should still list Friday’s QQQ book, not only the open sleeve.
- Inspector **underlying tape** and Charts **inspect** can show different sessions for the same name (trade_board pack vs `live_bars?date=`).
- Home hero “INSPECT” and Charts inspect are two code paths (`hero` vs `inspect`). Gesture work has to land on **both**, or Home should only route to Charts.

### 1.5 Other graphs (same drawer family)

- Home hero account/equity: range tabs only, **no brush**, hover-only scrub on desktop.
- Inspector option-path line: same inspect binder, no zoom around the mark jump.
- Replay is a VCR with ±1; it is **not** the live inspect chart and stays out of the dock.
- `barChart` still uses undersized canvas labels (`drawing.md`: 8px). Prefer HTML `signedBars` or 12px + fewer bars.
- Workspace multi-pane `drawXhair` has **no touch** handler. Phone Charts must not grow a 2×2.

**Not this:** MACD/RSI/fib/drawing tools, green/red live candles, a second chart library, putting the tall tape on Home.

---

## 2. Home still explains too little / shows too much

Slice A from `docs/ui-advanced-pass.md` is only partly done.

- Two Display numbers at once (clock **and** balance). One should yield.
- Hidden `#homeKpis` / `#portfolioDelta` still exist as a parallel accounting strip.
- Market / Models / Desk directory energy still leaks through details; phone Home should be explain → one number → one equity line → closest-to-fire → open sleeve.
- Weekend watchlist is a blank “no live setups” with no next-window time as the primary sentence (copy exists in explain, but the watch panel repeats the empty).
- 10px padding/gaps still sit off the 8-point grid in places.
- Production monitor Home is still the operator Home (GCP is down; do not expand Connect while fixing).

---

## 3. Book, Inspector, reconciliation (honest leftovers)

Fixed on the live book, do not regress: Home open +$5, Inspector live mark, closed missing fields say **NOT CAPTURED**, overnight OPEN counted in session blotter, reconciliation not “COMPLETE” with $0 fees.

Still open:

- Recovered **#12** is a legacy/MACD sleeve: direction, greeks, spread, fees, slippage, candidates are **NOT CAPTURED**. Leave them. Do not reconstruct.
- Account daily change **−$15** vs session **+$5** (difference −$20) is labeled, but the operator still has to trust a paragraph. Keep the warning; do not silently plug the gap with broker history.
- Quote **STALE** / session scan **STALE** is correct pre-open; the banner is doing its job.
- Activity debrief composer still competes with the book on a tall phone (book is first now; keep it that way).
- PDT / 0DTE / orders interlocks: do not touch this morning unless the user names them.

---

## 4. Lab / Models

- Lab table now loads `research_metrics` instead of the `{today:{}}` stub. Samples are **COLLECTING** (n days small). That is data, not a UI lie.
- Stretch / coverage / pareto live under **More research** — easy to miss on phone. Fine for Lab density; do not hoist candles into Lab.
- Models expectancy is forward paper and often red. Do not restyle the cards to look healthier.

---

## 5. Ops (not UI, but blocking)

- **FamilyVault e2-micro** in `us-east1-c` is TERMINATED. Billing is on. Starting it is Always Free VM + external IP. Do not start unless asked.
- Local web PID 40992 / runner PID 39329 have been up since the weekend. Pre-open is a safe window to restart **web** for static/HTML. Do not restart the **runner** after 09:35.
- Isolated Playwright Flask on **8876** is leftover test process; unrelated to the desk.
- This problem list is uncommitted until asked.

---

## 6. Suggested order before 09:35

1. **Charts brush-zoom + touch scrub + reset**, volume locked to the same window, Y rescale, last-session copy on Live names.
2. Candle readability when n is large (resample / close-line) and kill the `startWait` black flash.
3. Home subtract (one Display, no duplicate KPIs) only if 1–2 land with time left.
4. Do not promote to `main` or bounce production during the weekday session.

Verify on the local desk at 390 / 768 / 1280, then `/?intro=skip`. Paper only. `CEG_ALLOW_BROKER_ORDERS` stays false on this web.
