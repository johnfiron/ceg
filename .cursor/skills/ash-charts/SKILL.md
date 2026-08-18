---
name: ash-charts
description: ASH Terminal chart and drawing system. Use when adding or changing canvas plots, sparklines, candles, volume, histograms, trade overlays, 3D surface, crosshair, setup/coverage/pareto bars, or choosing HTML vs canvas in static/index.html.
---

# ASH charts

Full contract: [docs/ui-rulebook.md](../../../docs/ui-rulebook.md). Internals: [drawing.md](drawing.md). Sisters: `ash-type` (canvas fonts), `ash-color` (series color), `ash-layout` (one chart on phone).

## Goal

Pick the **existing drawer** that matches the question. Extend it. Do not add Chart.js, D3, or a second canvas stack. Agents who skip this skill draw a new sparkline with ad-hoc `getContext('2d')` and break DPR, dark fill, and touch.

## Primitive: always `resize(canvas, fillBlack=true)`

```js
function resize(c, fillBlack=true){
  let d=devicePixelRatio||1, r=c.getBoundingClientRect();
  c.width=Math.max(1,r.width*d); c.height=Math.max(1,r.height*d);
  let g=c.getContext('2d');
  g.setTransform(d,0,0,d,0,0);  // draw in CSS pixels
  g.clearRect(0,0,r.width,r.height);
  if(fillBlack){ g.fillStyle='#030303'; g.fillRect(0,0,r.width,r.height) }
  return {g, w:r.width, h:r.height}
}
```

- Bitmap = CSS box × DPR (sharp on phones).
- Coordinates after transform = **CSS px** (`w`, `h`).
- `fillBlack=false` only for `spark` (parent already dark).
- CSS: `.chart` 250px, `.chartTall` 430 / 330 phone, `.miniChart` 160, `.spark` 48. Phone **main** plot ≥ 200px.

Never assign `c.width` outside `resize`. Call `resize` at the start of every draw (window `resize` already re-renders pages).

## Decision: HTML vs canvas

| Question | Use | Why |
|---|---|---|
| Score / % / coverage in 0–1 | **HTML** `setupBar` / `covBar` | Selectable, CSS, no DPR bugs, fine at 44px tall |
| Ranked counts (miss reasons) | **HTML** `reasonBars` | Horizontal labels readable on phone |
| One number over time | **canvas** `line` | Path perception (Cleveland/McGill) |
| OHLC path | **canvas** `candles` | Wick/body; ash/grey already not hue-only |
| Volume with price | **canvas** `volumes` **under** candles, same `upto` | Shared x, separate y |
| Thumbnail beside a price | **canvas** `spark` | Illustration only — number is the encoding |
| Signed P&L by ≤8 short IDs | `barChart` or HTML bars | `barChart` labels are 12px with `+`/`−`; prefer HTML if names are long |
| This fill’s tape | **canvas** `tradeChart` | Only drawer with OR + VWAP + IN/OUT |
| Stretch vs fire | **canvas** `histChart` | Threshold lines baked in |
| RSI×CP×RVOL cloud | `drawSurface` | Lab/desktop; not Home |

If it can be a **sentence + one number**, do not chart it.

## Which function is best (do not invent a sibling)

| Function | Inputs | How it draws | Use | Do not use |
|---|---|---|---|---|
| `line(c, pts, key, color)` | array of objects, numeric `key` | min/max y, X pad 34, Y pad 11/30, 4 `#171717` grids, one stroke 1.65px `#e7e7e1` | Equity `cumPnl` | Two series, categories, OHLC |
| `barChart(c, rows, key, label)` | rows, value key, label key | **zero at h/2**, up green `#4ee693` / down `#ff626c`, 12px labels with `+`/`−` | Strategy/ticker P&L desktop | Time, long labels, phone |
| `candles(c, arr, upto)` | `{o,h,l,c}[]`, optional end index | y from min(l) max(h), wick line + body rect, up `#dcded8` down `#72746f` | Replay, MTF, workspace | P&L, counts |
| `volumes(c, arr, upto)` | same bars `.v` | columns from bottom, weak tint | Paired with candles | Alone |
| `spark(c, bars)` | `.c` closes | 4px inset polyline `#73bfff` 1.2px, no grid | Live-row thumbnail | Primary chart |
| `histChart(c, bins)` | `{mid,fire,miss}[]` | dual columns + dashed ±1.25 ATR | MVR lab only | Generic hist without forking |
| `tradeChart(c, pack)` | `bars` + `or_*` + `vwap_*` + indices | candles + OR dash `#73bfff` + amber cone + VWAP `#f1b94e` + IN/OUT | Open/closed trade cards | Market overview |
| `drawSurface(points)` | `{rsi,cp,rvol,pnl}` | 3D project, drag on `pointermove` | Lab | Phone Home; claims |
| `drawXhair(c, frac)` | 0–1 | dashed violet x at pad 38 | Linked panes **plus DOM readout** | Hover-only |
| `chartEmpty(c, opts)` / `startWait(c,{busy})` | canvas, optional `{busy, summaryId, summary}` | 9–16 lit bone plates (`drawLitFlakeOn`, `230,230,224`). Busy = rAF until `resize()`; empty freezes at 4s | In-flight fetch or no data | Data ink, spinners, colored ash |

Replay: `candles(replayChart, bars, i)` + `volumes(replayVolume, bars, i)` — **same `i`**. Workspace: `candles` + `drawXhair` on mousemove (touch still missing — add tap/step when changing this).

## Required companions

Canvas has no accessibility tree.

1. DOM title = the question (“Realized P&L since first fill”).
2. Last value or takeaway in DOM (Body/Numeric).
3. `aria-label` or summary text.
4. Line weight ≥ 2px on phone; canvas `g.font` ≥ 12px (`ash-type`).
5. Direct-label last point instead of a 7px legend.
6. `prefers-reduced-motion`: replay interval and surface drag still need buttons (`stepReplay` already exists).

## NN/G

One question per chart. Bar/line/scatter beat pie/area/3D. Stacked bars have high error — don’t add them. Contrast the finding; mute the rest (`ash-color`).

## Don’t

- New plotting library for one panel.
- 2×2 / 3×2 candle grids on `<850px` (`ash-layout`).
- Hover as the only inspect gesture.
- Encoding a fact **only** in a spark or a 6px matrix cell.
