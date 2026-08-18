---
name: ash-type
description: ASH Terminal typography system — type roles, rem scaling, tabular numbers, and canvas g.font. Use when changing fonts, font-size, letter-spacing, KPI/label copy, numeric displays, Inter/system stack, or any text in static/index.html CSS or canvas fillText.
---

# ASH type

Full contract: [docs/ui-rulebook.md](../../../docs/ui-rulebook.md) §1.3 / §1.6. Identity first: `ash-identity`. Sisters: `ash-charts`, `ash-color`, `ash-layout`.

Labels stay **open** tracking (stamp). Display/numbers stay **tight**. Body tracking is 0 — do not letter-space sentences to feel more “ASH.”

## Goal

One scale for CSS **and** canvas text so Home, Lab, and plots feel like one product. Agents already know typography; they do not know this app’s roles or that canvas ignores CSS `font-family`.

## Roles (use these names in CSS variables)

| Token | Size | Weight | Line-height | Tracking | Use |
|---|---|---|---|---|---|
| `--t-display` | 2–2.5rem (32–40px) | 700–800 | 1.1 | −0.03em | Equity, clock |
| `--t-title` | 1–1.25rem (16–20) | 650–700 | 1.25 | −0.02em | Panel h2, explain head |
| `--t-body` | **1rem (16)** prefer 15–16px | 400–500 | 1.5 | 0 | Sentences, explain |
| `--t-meta` | 0.8125–0.875rem (13–14) | 400 | 1.45 | 0 | Secondary |
| `--t-label` | **0.6875–0.75rem (11–12)** | 600 | 1.3 | +0.06em | Chips, KPI captions, nav |
| `--t-numeric` | 0.875–1.125rem (14–18) | 600 | 1.2 | 0 | Prices, P&L, % |

**Floor 11 px / 0.6875rem.** Apple HIG iOS min 11 pt; Material label-small 11; body 14–16. Do not add 7–9 px classes.

ASH labels stay **uppercase + tracked + heavy** at that floor. The look is the stamp, not the 7px. Serif = orb/boot A only (`ash-identity`).

## Family

```css
--font-ui: system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
--font-numeric: inherit; /* add tabular via feature, not a second file unless loaded */
```

`font-family: Inter, …` is a lie until Inter is linked. Prefer system stack, or load Inter (and still scale). Serif = brand orb only. WWDC26: custom fonts must honor user text size.

## Numbers

On every money / % / RVOL / score / table numeric cell:

```css
font-variant-numeric: lining-nums tabular-nums;
font-feature-settings: "lnum" 1, "tnum" 1;
```

Right-align. Fixed decimals (`money()`, `pct()`). Heavier than the label beside them. Smashing fintech guide: proportional digits jitter live marks.

## How text is actually drawn here

| Surface | Mechanism | Trap |
|---|---|---|
| DOM | CSS on `.heroValue`, `.sub`, `.kpi span`, `.metric`, `table`, `.nav` | Dozens of one-off `font-size: 7px`–`9px`. Map each to a role; do not add an 8th size. |
| Canvas | `g.font = '11px system-ui'` after `resize()` | **Ignores CSS.** `barChart`, `tradeChart` markers, `histChart` use **8px**. If you bump CSS labels to 12, bump these too or plots look like a different app. |
| Empty states | `fillText('Awaiting data', 14, 24)` | Use 12px+, `--text-mid`, Body-sized. |

`resize()` maps drawing to CSS pixels. `g.font` sizes are CSS px, not device px. Good. Still set ≥12 for any label a user must read on a phone.

## Do

- Size in `rem` / `clamp` (WCAG 1.4.4 resize 200%).
- Wrap, don’t truncate, at large text (Apple Dynamic Type).
- Keep hierarchy when scaling: Display stays > Title > Body > Label.
- Explain copy stays Body (the 11–16 px explain box is the voice to copy).

## Don’t

- Letter-space body sentences.
- Ultralight/thin weights on dark `#000`.
- Mix Inter + Roboto + Georgia in one panel.
- Shrink type to fit a 4-column KPI row — drop columns (`ash-layout`).
