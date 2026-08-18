# Canvas drawing internals

Source: `static/index.html` functions `resize`, `line`, `barChart`, `candles`, `volumes`, `spark`, `histChart`, `tradeChart`, `drawSurface`, `drawXhair`. CSS plot boxes: `.chart`, `.chartTall`, `.miniChart`, `.spark`.

Agents extend these. Copy the pad/scale math; do not guess.

## Shared scale pattern

Most price drawers:

```text
X(i) = left + (w - left - right) * (i + 0.5) / n
Y(v) = top + (h - top - bottom) * (1 - (v - lo) / (hi - lo))
```

| Drawer | left | top | right | bottom | lo/hi |
|---|---|---|---|---|---|
| `line` | 34 | 11 | 8 | 30 | min/max of `key` |
| `candles` / `tradeChart` | 38 | 10 | 8 | 27 | min(l) / max(h) (+ OR in tradeChart) |
| `spark` | 4 | 4 | 4 | 4 | min/max close |
| `volumes` | 0 | — | 0 | 0 | 0 … max(v), y from bottom |
| `barChart` | 0 | — | 0 | — | zero at `h/2`, mag from max |abs| |

If you overlay two canvases (replay price + volume), **same `upto` and same n**. They do not share y.

## `line`

- Filters non-finite `pts[i][key]`.
- Empty → grey `fillText` at (14,24).
- Degenerate range → `lo-=1; hi+=1`.
- Grid: 4 horizontal strokes `#171717` from x=34 to w-8.
- One path, `lineWidth` 1.65, default stroke `#e7e7e1`.
- **No** axes, last-value label, zero line, or markers.

To add a zero line or last label, draw after the stroke using the same `X`/`Y`. Do not start a second `line()` call for a second key — it would rescale independently and lie.

## `candles`

- `arr.slice(0, upto)` for replay scrub.
- Body width `max(1, (w-46)/n * 0.56)` — at many minutes this becomes 1px (wick-only). On a phone with a full RTH session, prefer resampling (5m) or a line of closes rather than 390 1px candles.
- Up/down is **close ≥ open**, colors ash/grey (good: not green/red only). Keep that.
- No VWAP, OR, or volume. Those are `tradeChart` / `volumes`.

## `volumes`

- Full width, bars from bottom, height `(h-8)*v/max`.
- Fill `#d8ddd744` up / `#77777755` down — decorative, not a second encoding. Price meaning stays on `candles`.

## `spark`

- `resize(c, false)` — does not paint `#030303` (row background shows through).
- No empty-state text.
- Stroke `#73bfff` 1.2px. Thumbnail only.

## `barChart`

- Zero midline. Positive up, negative down.
- Color-only P&L (`ash-color` violation). When touching this, add `+`/`−` in labels or hatch.
- `g.font='8px system-ui'` — too small; 12px and fewer bars, or switch to HTML.

## `histChart`

- `bins[].fire` / `.miss` / `.mid` (ATR stretch).
- Miss `#2a2a28`, fire `#4ee693`, threshold dash `#f1b94e55` when `mid ≈ ±1.25`.
- Labels −3 / 0 / +3 ATR at 8px.
- Fork for a new histogram; don’t overload MVR meaning.

## `tradeChart`

Richest drawer. Order of paint (back → front):

1. Grid
2. OR high/low dashed `#73bfff55` (if present)
3. VWAP cone fill `rgba(241,185,78,.08)` using `vwap_hi`/`vwap_lo`
4. Candles (same ash/grey as `candles`)
5. VWAP line `#f1b94e` 1.4px
6. `marker(entryIndex, sideColor, 'IN')` — CALL green / PUT red (hue + label; keep the word)
7. `marker(exitIndex, violet, 'OUT')`
8. Last underlying 8px bottom-left

`bars.indexOf(b)` inside cone loop is O(n²). Fine for one session; don’t copy for 10 charts.

## `drawSurface`

- Maps rsi, close position, rvol → 3D then perspective.
- Rotation: `pointerdown`/`move`/`up` on `surfaceCanvas` (drag). WCAG 2.5.7: needs a non-drag alternative if you keep it.
- Point color: null pnl grey, else green/red (hue-only). Lab only.

## `drawXhair`

- Uses **CSS** `getBoundingClientRect` + current 2d context **without** going through `resize`. It assumes candles just redrew.
- `frac` 0–1 along plot (pad 38).
- Workspace `onmousemove` redraws **all** panes then xhair. Fine for 1–2 charts; expensive for 6. No touch handler.

When adding inspect: store `xhair`, on tap set frac, draw readout in a DOM node (time + OHLC). Do not leave the value only on the canvas.

## HTML bars (not canvas)

- `setupBar(s)`: width = `s.score` 0–1; classes `hot` if fired, `armed` if ≥0.85. CSS `.setupBar` height 5px — bump toward 8–12 if touching layout.
- `covBar(p)`: completeness; classes `mid`/`low`.
- `reasonBars(rows)`: `[label, count][]`, track width vs max.

Use these for gates and counts. They survive zoom and screen readers better than canvas.

## Empty and error

All canvas drawers should `fillText` at ≥12px if there is no data. Do not leave a black rectangle. Trade board already swaps to a `.sub` string on fetch error — prefer DOM for errors.
