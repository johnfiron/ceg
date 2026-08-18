---
name: ash-identity
description: ASH Terminal visual identity — bone-on-void cinema, ember ration, grayscale candles, ash particles, serif mark. Use when restyling, choosing a look, adding motion, intro themes, or when a change might drift toward Bloomberg neon, Material dark, or generic SaaS.
---

# ASH identity

Full contract: [docs/ui-rulebook.md](../../../docs/ui-rulebook.md) §1.1–1.7. Load this **before** type/charts/color/layout on any visual pass. Title-screen matter/light/A: `ash-intro`.

## One sentence

ASH is **what is left after the fire**: bone type on a true-black void, falling ash, a serif A, and a quiet desk. Color is rationed. Cinema is the door, not the session.

## Already in the product (do not “clean up”)

| Artifact | File / id | Meaning |
|---|---|---|
| `#000` + `--ash` `#deded8` | `:root` | Dark-first, not Material `#121212` |
| `ambientAsh` flakes | `spawnAsh` / `ashFrame` | Atmosphere. Pale `230,230,224` only |
| Candle storm + serif A | `stormFrame`, `drawBrandedA` | Film-title boot. **Candles are a matter option**; flakes are the original / identity default (`ash-intro`) |
| Vaporize pages | `vaporizeTransition` | Physical cut, curl-noise wind |
| Live `candles` ash/grey | `#dcded8` / `#72746f` | Price is monochrome |
| Intro palettes | `INTRO_PALETTES` | Costumes. **white** = identity; market/pink optional |
| Tracked eyebrows | `.eyebrow`, `.brandText span` | Stamped metadata |
| Orb + Georgia A | `.brandOrb` | Only serif |
| Amber | VWAP, armed, stale | Ember — the 3% accent |

## Steal / refuse

Take grammar from **Sequel** (void + linen + pills — closest chrome), A24 cinema (absence), iUSPC ember ration, TradeX “red/green = direction only,” soft brutalism (heavy type + usable pills).

Refuse: Bloomberg/synthwave neon, Linear cyan, glass-as-brand, rainbow TradingView, hacker green, Sandclock mint-as-brand, gold luxury skeuomorph, Material You. Do not swap `#000` for warm charcoal `#0c0a09`.

## Atmosphere vs desk

- Atmosphere (`#ambientAsh`, `#introCanvas`, `#fxCanvas`): `pointer-events: none`, under/over the app, never on the plot’s data ink.
- Desk: panels, explain, numbers, `resize()` charts.
- Cinema is the **door** (Linear: no hero video in the product; BQuant particles were a *launch*). Idle flakes under Home are atmosphere, not identity you must keep moving.
- **WCAG 2.2.2 (A):** `ashFrame` auto-starts, loops >5s, and runs next to reading content → needs pause/stop/hide. `prefers-reduced-motion` is 2.3.3 AAA and does **not** replace 2.2.2. Gate `requestAnimationFrame` with `matchMedia` — CSS cannot stop it.
- Boot storm is exempt only while it is the only view. After `finishIntro()`, stop it.

## Type voice

Identity = **uppercase + tracking + weight** on labels, **tight heavy bone** on the hero number, **sentence case** on explain. Raising 7px labels to 11px does **not** break the look if tracking/case stay. Serif never enters the blotter.

## Color ration

~95% charcoal/bone. Amber = ember. Blue = tape/progress. Violet = inspect. Green/red = **up/down only**, always with `+`/`−` or a word (`ash-color`). Do not recolor live candles to traffic lights to “look like trading.”

## Motion

Boot once (flakes **or** candles, same light) → idle ash → vaporize on `go()`. Desk stays still. No bounce, no colored bursts, no particle headings on every panel. Title-screen lighting and the path-A live in `ash-intro`.

## Genre (steal grammar)

- **Ceremony:** title-card / BQuant particles — once.
- **Masthead:** editorial stamp (tracked caps, serif A only). Yoshiki: color ~3%, gold is a line.
- **Instrument:** Linear/Raycast quiet desk — hairlines, 5% accent, 20px chrome blur max. Not Material, not TradingView rainbow.

Warm **ink** (`#f5f5f1`, `#deded8`) on a **cold void** (`#000`). Do not warm the stage to `#0c0a09` and do not ice it to Linear `#010102`.

## Agent check

Would this still read as ASH if you turned color off **and** paused the flakes? If no, it is a costume, not the product.
