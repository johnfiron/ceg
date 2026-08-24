# ASH UI implementation specification

This specification covers a **layout and inspect-chart** pass on ASH Terminal. This is not a restyle, not a new product, and not a TradingView or Robinhood clone.

The operator’s complaint: Home feels cluttered; they do not know what several panels are for; charts are everywhere; they still leave the desk for Robinhood / TradingView / similar to *look at a real tape*. They want that capability **advanced here**, in **this app’s material**, without stealing those products’ chrome.

## Shipped structure — 2026-08-24

The implementation now uses the contract in this document: Home has one account chart and routes tape work to Charts; Charts owns one inspect lifecycle with a persistent time window and paired volume; Activity is the grouped book; Models leads with strategy understanding and links to Replay; Replay is one price/volume instrument with explicit transport; Lab extras are purpose-based and lazy; Settings is ordered by health, integrity, preference, notification, and backup jobs. Preserve that hierarchy in later passes.

Read this file completely. Then follow **Order of operations**. Do not start drawing until you have read the rulebook identity sections and loaded the skills below.

---

## 1. What this product is

ASH is a **phone-first paper session desk**. Cinema is the **door**. After ENTER, the session is a **quiet instrument**.

- Home **explains the current window** and shows the book.
- Charts **inspects one tape** against the setup this desk actually trades.
- Activity **is the book** (open/closed fills). Not a second market overview.
- Models explain **why a sleeve fires**.
- Lab holds **research density**.
- Replay is a **research VCR** (no future bars). Hidden from the dock.

Paper only. Do not point `PAPER` at live Alpaca. Web and runner are separate processes. Do not bounce the runner in OPN/OSF/ORB/VRC/MVR/15:45 unless the user asked. If you touch Activity, PDT, 0DTE, or reconcile, also load `docs/development/guides/ash-desk/guide.md`.

Production `/ash` (FamilyVault) is a **read-only monitor**. It must not grow Connect, key fields, or order-arming chrome.

---

## 2. Order of operations (mandatory)

1. Read [`docs/ui-rulebook.md`](ui-rulebook.md) **§1.1–1.8 first** (identity), then §3 (drawers), §4–6 (charts / color / layout), §7–8 (balance + shipped).
2. Load [`docs/development/guides/ash-identity/guide.md`](../docs/development/guides/ash-identity/guide.md). Stop if the work would drift to Bloomberg neon, Material `#121212`, Linear cyan, or TradingView rainbow.
3. Load only what you will touch:
   - Home / grids / nav / touch → [`ash-layout`](../docs/development/guides/ash-layout/guide.md)
   - Any canvas or bar → [`ash-charts`](../docs/development/guides/ash-charts/guide.md) **and** [`ash-charts/drawing.md`](../docs/development/guides/ash-charts/drawing.md) **before** editing a drawer
   - Type / `g.font` → [`ash-type`](../docs/development/guides/ash-type/guide.md)
   - Up/down, tokens → [`ash-color`](../docs/development/guides/ash-color/guide.md)
   - Boot / A / flakes → [`ash-intro`](../docs/development/guides/ash-intro/guide.md) — **do not rebuild**
4. Reuse `resize()` and existing drawers in [`static/index.html`](../static/index.html). **No Chart.js, D3, Lightweight Charts, TradingView widget, or second canvas stack.**
5. Phone (`max-width: 850px`) is the source of truth. Desktop adds columns. Do not shrink type or charts to save a 4-column grid.

---

## 3. Shipped — do not redo

| Already done | Do not |
|---|---|
| Title engine (storm, path-A, flakes + white default) | Rebuild intro, 26-letter alphabet, WebGL |
| Type tokens `--t-display` … `--t-label`, 11px floor, canvas labels 12px | New type scale, Inter, 7–9px desk type |
| Phone tables card-stack below 850px | `min-width: 800px` as the only table view |
| Nav / `.btn` / `.icon` 44×44 | Hover-only primary actions |
| 850px collapse of `.grid2`, 2-up `.kpis`, 1-col `.strategyGrid` | New breakpoint system |
| Live candles ash/grey (`#dcded8` / `#72746f`) | Traffic-light live candles |
| Void `#000`, bone `--ash` / `--text`, amber ember ration | Warm charcoal `#0c0a09`, mint-as-brand |
| Replay out of the dock; ±1 step exists | Add Replay as a sixth dock item |
| Monitor lock / skip-intro (`desk_configured`, `from=vault`, `ASH_BASE`) | Re-enable Connect on production web |

**Identity check:** would this still read as ASH with color off **and** flakes paused? If no, stop.

---

## 4. Product thesis (charts)

Robinhood = broker storefront (“should I buy this name”). TradingView = drawing terminal (indicators, tools, rainbow). **Do not become either.**

ASH’s advanced chart is: **price versus the setup this desk trades**, in this desk’s material.

Allowed on the inspect surface:

- One **tall** ash/grey `candles()` plot
- `volumes()` **under** it, **same `upto` / same n**
- Overlays the models already use: prior close / gap, 09:30–10:00 opening-range box, session VWAP, entry / exit. Grammar already lives in `tradeChart`
- DOM title (a sentence) + tap/step readout (not hover-only). Last price and the comparison in **text**
- The **option you hold** as a second fact (symbol, expiry, mark, your fill) — not a second rainbow pane

Forbidden on that surface:

- MACD / RSI / Bollinger / fib / drawing toolbar / multi-indicator soup
- Green/red live candles
- 2×2 or 3×2 panes on phone
- A new chart library
- Putting this inspect plot on Home

**Home almost stops charting.** At most one equity `line` (the book). Closest-to-fire is HTML `setupBar` + a number. If it can be a sentence and a number, it is not a canvas.

**Lab does not grow candles.** Distributions, miss bars, debrief. `drawSurface` stays Lab/desktop.

**Replay** stays a no-lookahead VCR. Not the live inspect chart.

---

## 5. Layout thesis (clutter)

The user does not need more panels. They need fewer things that have a **job in the current `session_clock` window**.

Contract Home order ([`ash-layout`](../docs/development/guides/ash-layout/guide.md)):

1. Explain (`#explainBox`)
2. **One** Display number
3. **One** supporting chart (equity `line` only)
4. Closest to fire (`setupBar` list)
5. Open trades / exits
6. Everything else → Charts / Activity / Models / Lab

Live `#home` (approx. lines 371–408) currently stacks: Now + **Display clock** + explain, then **second Display** equity + subtitle + **four KPIs** + equity chart, then closest-to-fire **and** opens, then **three directory cards** (Market / Models / Desk), then two `<details>`. That is the clutter.

Also:

- `#portfolioDelta` already states realized / cash / open / broker day; `#homeKpis` repeats it
- `renderHomeSummaries` uses `status.broker_orders_enabled` from the **web** process. Production web is always unarmed. Do not put that lie on Home. Monitor cannot see runner arming unless you add a runner-written snapshot (desk work, not a guess)
- `.app` padding `10px` and many `gap:10px` are off the 8-point grid (4 / 8 / 12 / 16 / 24 / 40)
- `.settingsGrid` does **not** collapse at 850px
- Activity opens with three debrief textareas; the book is below. Invert: book first, composer last
- Production `/ash` still uses the full operator Home. Give it a quieter hierarchy (same HTML file, `ASH_BASE` / production class) — not a new app

Dock stays ≤5–6: Home, Activity, Charts, Models, Lab. Settings stays the top ⚙ **or** moves into the dock — pick one. Do not add Replay.

---

## 6. Suggested slices (ship in this order)

Do not mix a restyle into these.

### Slice A — Home subtract (phone-first)

**Files:** `static/index.html` (markup ~371–408, CSS Home grids, `renderHome` ~2448).

- One Display: either `#sessionClock` **or** `#portfolioValue`. The other becomes `--t-title` or a chip.
- Remove or fold `#homeKpis` into the subtitle.
- Keep explain → number → equity chart (`.chart` ≥ 200px) → closest-to-fire → open trades.
- Default-hide Market / Models / Desk cards and Home `<details>` on phone (dock already goes there, or one “More” disclosure).
- Do not show web `broker_orders_enabled` as operational truth.
- Nudge Home spacing onto the 8-point grid while you are in those rules.

### Slice B — One inspect chart on Charts

**Files:** `static/index.html` Charts section ~411–429, `candles` / `volumes` / `tradeChart` / `drawXhair`, [`drawing.md`](../docs/development/guides/ash-charts/drawing.md).

- Phone: one column, **one** tall plot (use `.chartTall` 330 on phone). Hide 2 / 2×2 / 3×2 (already hidden below 850).
- Desktop may keep a name list beside the tall plot. Do not paint nine equal mini-charts as the primary.
- Pair `volumes` under `candles` with the same `upto`.
- Add **tap + step** crosshair and a DOM readout (`ash-charts` required companions). Hover-only is a known gap; do not ship inspect without a button/stepper.
- Overlays: prior close, OR, VWAP, IN/OUT — extend `tradeChart` / `candles`, do not fork a fourth price drawer.
- Full RTH 1-minute on a 390px phone becomes 1px wicks. Resample (5m) or a close line for the full session; keep 1m for a shorter window. See `drawing.md` on `candles`.
- Live name list can stay HTML rows + last price; `spark` is thumbnail only, never the only encoding.

### Slice C — Activity + monitor quiet

- Activity: open fills, then closed, then debrief. Hide Reconcile / export / key settings when production web / `WEB_READ_ONLY` / `ASH_BASE`.
- Collapse `.settingsGrid` at 850px.
- Monitor (`ASH_BASE` or `from=vault` or `environment===production`): hide Lab research dump, intro costume, Replay, Connect. Home is clock, book number, open row, way into Charts.

### Slice D — only if asked

WCAG 2.2.2 idle-ash pause (rulebook §1.6). Not this pass unless the user names it.

---

## 7. Technical constraints

- One UI file: [`static/index.html`](../static/index.html). CSS at top; drawers via `resize()`.
- After `resize()`, draw in **CSS pixels**. Never set `canvas.width` yourself.
- If you change a CSS type size, change the matching `g.font` (desk canvas ≥ 12px).
- Hue is never the only up/down cue (`+`/`−` or a word). `barChart` already labels signs; live `candles` stay grey.
- Touch 44×44. List rows ~44. No readable text &lt; 11px (boot `.small` 8px is ceremony only).
- Safe area already on `.app`, `.topbar`, `.bottomNav`. Sticky nav must not cover a focused field (WCAG 2.4.11).
- `prefers-reduced-motion`: do not rely on CSS alone to stop `requestAnimationFrame`.
- Tests: string contracts in [`tests/test_safety.py`](../tests/test_safety.py) (`ASH_BASE`, `applyMonitorLock`, `from=vault`). Do not remove those strings. Add assertions if you add a monitor class name the tests should lock.
- Do not commit secrets or `config.*.json` with keys.

---

## 8. Files to open (in order)

1. This file
2. `docs/ui-rulebook.md`
3. `docs/development/guides/ash-identity/guide.md`
4. `docs/development/guides/ash-layout/guide.md` (and `ash-charts` + `drawing.md` for slice B)
5. `static/index.html` — CSS ~75–293, `#home` 371–408, `#charts` 411–429, `#activity` 540+, `renderHome` ~2448, drawers ~2216+
6. Context only: `docs/analysis/06-desk-ui-and-identity.md`, `docs/analysis/01-process-and-authority.md` (web status ≠ runner armed)

---

## 9. Balance checklist (before you finish)

- [ ] No readable text &lt; 11px (CSS **and** `g.font`)
- [ ] Numeric values tabular + signed
- [ ] Hue is not the only up/down cue
- [ ] Every canvas has a DOM title + last value / takeaway
- [ ] Phone: one column, main inspect plot ≥ 200px (tall if it is the Charts object), tap ≥ 44px
- [ ] Same token in CSS and canvas for a given meaning
- [ ] Still reads as ASH with color off and flakes paused
- [ ] No new chart library
- [ ] Intro / A / void / grey candles untouched
- [ ] Production monitor still cannot Connect or arm
- [ ] `python -m unittest tests.test_safety -v` if you touched `index.html` strings the tests grep

---

## 10. How to talk to the operator

Implement **one slice per turn** unless they ask for more. Describe the information hierarchy you changed, not a new “look.” If they ask to make it “more like TradingView,” refuse the chrome and offer the inspect-surface thesis in §4.

If scope is unclear, default to **Slice A only**.
