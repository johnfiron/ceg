---
name: ash-color
description: ASH Terminal color, contrast, and non-hue encoding. Use when changing CSS variables, up/down P&L, candle colors, chart series, chips, status dots, dark-UI palettes, or WCAG contrast for text and graphics.
---

# ASH color

Full contract: [docs/ui-rulebook.md](../../../docs/ui-rulebook.md). Sisters: `ash-type`, `ash-charts`, `ash-layout`.

## Goal

Dark UI that still passes WCAG, and **direction that a color-blind user can read**. Do not add new greens/reds. Tune `--green` / `--red` / `--muted` and always pair hue with another channel.

Amber is the **ember** (identity): VWAP, armed, stale — not a second brand. Green/red are direction only. Live candles stay ash/grey. See `ash-identity`.

## Tokens (reuse, don’t fork)

From `:root` in `static/index.html`:

| Var | Job |
|---|---|
| `--bg` `#000` | Page |
| `--text` `#f5f5f1` | Primary reading (≥ 4.5:1) |
| `--muted` `#858783` | Meta only if it still hits 4.5:1 at < 18px |
| `--green` / `--red` | Up / down **plus** sign or word |
| `--amber` | Warning, VWAP, armed |
| `--blue` | Setup/progress, sparks |
| `--violet` | Crosshair, OUT marker, pareto |
| `--line` | Hairlines, not data |

Add `--text-mid` / `--text-lo` rather than random `#777` / `#7f817c` / `#747670` (canvas labels). Those greys on `#040404` often fail 4.5:1.

## Contrast floors

| Kind | Ratio | Source |
|---|---|---|
| Normal text (< 18px, or < 14px bold) | **4.5:1** | WCAG 1.4.3 AA |
| Large text | 3:1 | 1.4.3 |
| Chart lines, bars, icons, focus, input border | **3:1 vs adjacent** | 1.4.11 |
| Two series that touch | 3:1 **between** them or a second cue | 1.4.11 + 1.4.1 |

Dark mode is not a free pass. Recheck every pair on `#000` / `#030303` / `#040404`.

## Never hue alone (1.4.1)

| Today | Problem | Required extra cue |
|---|---|---|
| `.up` / `.down` on P&L | Deuteranopia | Prefix `+`/`−` (live tape already does for %). Keep it on money too |
| `barChart` fill green/red | Same | Label includes sign or hatch |
| `drawSurface` / hist fire color | Same | Shape, pattern, or DOM legend with words |
| Candles ash/grey | **Better** — keep; don’t “fix” to traffic lights |
| `setupBar` blue/amber/green | Position (width) already encodes score — OK if class isn’t the only meaning |

Status FIRE / DNT / STALE: **word on the chip**, not only a 6px `.statusDot`.

## Series palettes

- One series: `--ash` / `#e7e7e1` (`line` default) on black — high contrast.
- Two series: Paul Tol high-contrast (survives greyscale): `#004488` / `#DDAA33` (optional `#BB5566`). Source: https://personal.sron.nl/~pault/
- Qualitative >2: Tol bright or ColorBrewer qualitative, then **direct labels**, not a tiny legend.
- VWAP already amber; OR already blue — don’t recolor those without updating `tradeChart`.

## Canvas vs CSS

Changing a CSS variable does **not** recolor canvas. Hardcoded fills:

- `line` `#e7e7e1`, grid `#171717`
- `barChart` `#4ee693` / `#ff626c`
- `candles` `#dcded8` / `#72746f`
- `spark` `#73bfff`
- `histChart` miss `#2a2a28`, fire `#4ee693`, threshold `#f1b94e55`
- `tradeChart` OR/VWAP/IN/OUT as in `ash-charts` drawing.md

If you introduce CSS series tokens, **read them in JS** (`getComputedStyle`) or keep a single `PALETTE` object both CSS and canvas use. Do not let Home KPI green drift from `barChart` green.

## Don’t

- Neon on black that burns and still fails 3:1 between two neons.
- Grey body copy “for luxury.”
- Glass over the plot (NN/G Liquid Glass 2025).
- Encoding sample quality only in `.up` / `.amber` without the word COLLECTING.
