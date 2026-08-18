---
name: ash-layout
description: ASH Terminal mobile layout, spacing, touch targets, and Home information hierarchy. Use when changing grids, panels, bottom nav, tables, explain box, KPI rows, safe areas, tap targets, or phone vs desktop structure in static/index.html.
---

# ASH layout

Full contract: [docs/ui-rulebook.md](../../../docs/ui-rulebook.md) §1.2 / §1.6. Identity first: `ash-identity`. Sisters: `ash-type`, `ash-charts`, `ash-color`.

Blur stays on chrome only (~19px dock). Do not frost plots. Cinema is the door; the session is a desk.

## Goal

Phone is the source of truth. Desktop adds columns. Home **explains the session**; Lab holds density. Do not shrink type or charts to preserve a 4-column desktop grid.

## Breakpoint

Existing: `@media (max-width: 850px)` collapses `.grid2`, `.kpis` to 2, `.strategyGrid` to 1, `.chartTall` 330. Keep **850px**. Below it:

- One column for panels
- KPIs **2-up**, not 4
- Explain books **1 column** (already listed in the media query with `.explainBooks`)
- Charts page: `setLayout(1)` effectively — do not paint 2×2/3×2 candles
- Tables: cards or stacked metrics, never `min-width: 800px` as the only view (WCAG 1.4.10 reflow)

## Home order (decision UI)

1. Explain (`#explainBox`) — Title + Body
2. The number (`#portfolioValue` or open P&L) — Display
3. **One** supporting chart (equity `line`)
4. Closest to fire (list + `setupBar`)
5. Playbook / open trades
6. Everything else → Lab / Charts / Replay

If a panel does not change a decision in the current `session_clock` window, it is not on Home.

## Space

8-point grid: 4 / 8 / 12 / 16 / 24 / 40. Panel padding 16, gap 8–12, bottom nav clearance `padding-bottom` ≥ 100px **plus** `env(safe-area-inset-bottom)`.

Safe area is on `#bootOverlay`, `.topbar`, `.bottomNav`, and `.app` bottom padding.

## Touch (Apple 44, Material 48, WCAG AA 24)

| Control | Rule |
|---|---|
| `.btn`, `.icon`, `.nav` | min 44×44 CSS px (padding, not just glyph) |
| `.tab` / chips if tappable | same, or 8px+ gap so 24px circles don’t overlap (2.5.8) |
| Inputs | min-height 44 |
| Icon 20–24 | hit slop via padding to 44 |
| List rows (`liveRow`, `market`) | min ~44 height |

Bottom nav: thumb-zone, 6 items, labels at `--t-label` (11px), 44×44 hits.

## Gestures need a button

| Gesture now | Backup already / needed |
|---|---|
| Replay play | `stepReplay` exists — keep visible on phone |
| Surface rotate | drag only — add sliders/buttons if you keep 3D |
| Linked crosshair | `mousemove` only — tap + DOM readout (`ash-charts`) |

WCAG 2.5.1 pointer gestures, 2.5.7 dragging. WCAG 2.4.11: sticky `.bottomNav` / `.topbar` must not cover focused fields (settings).

## HTML vs canvas for layout

Progress and ranks = DOM (`setupBar`, `covBar`, `reasonBars`) so they wrap and zoom. Paths = canvas in `.chart` / `.miniChart` / `.spark`. Do not put a 160px `.miniChart` as the **only** Home chart; bump main plot ≥ 200px on phone.

## Density

`body.density-monitor` already hides some Lab. Do not use density as an excuse for 7px type. Prefer fewer panels.

## Don’t

- Hover-only affordances.
- Frosted glass over data (NN/G Liquid Glass, Oct 2025).
- New grid system (CSS grid with 1.18fr / 0.82fr is enough).
- Fitting the blotter on 390px by shrinking `table { font-size: 8.7px }`.
