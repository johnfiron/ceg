---
name: ash-intro
description: ASH Terminal title-screen ceremony — flake vs candle matter, color palettes, fake-3D plate lighting, and the path-drawn serif A. Use when changing the boot storm, introCanvas, ambient ash, intro settings tabs, brand orb, or title lighting. Do not rebuild the engine.
---

# ASH intro (title + mark)

Full contract: [docs/ui-rulebook.md](../../../docs/ui-rulebook.md) §1.6–1.8. Load `ash-identity` first. Do not restyle the desk.

**Choreography changed.** Do not keep the old 5.6s “already in a storm → spring into A.” The movie is in [docs/startup-animation-prompt.md](../../../docs/startup-animation-prompt.md): first-open fall to a ground plane, draft that wraps around a ring (not teleport), oval→circle, then a **15s settle into the A** with **no outline until full**. Flakes **fall into place**; they must not streak or bullet onto homes.

**ENTER cut** (after the A is holding) is a separate job: [docs/enter-cut-prompt.md](../../../docs/enter-cut-prompt.md). Mixture of through-the-ring + fingerprint gust + A going cold. Open screen formed by those flakes. Do not keep magnetic snap / vaporize rects as the door.

Keep: Canvas 2D, plate lighting, path-A as **home samples**, palettes, fingerprint ENTER, `needs-keys`. Flakes first. Do not add WebGL/Three.js to the phone boot.

Code: `#introCanvas` / `makeStorm` / `drawStorm` / `drawPathA` / `drawLitFlakeOn` / `drawLitCandleOn`, `#ambientAsh` / `ashFrame`, `.brandOrb` + `.orbA`, Settings matter/color/bar/gate/idle tabs.

## Two axes (orthogonal)

| Axis | `localStorage` | Values | Identity default |
|---|---|---|---|
| Matter | `ashIntroMatter` | `flakes` · `candles` | **`flakes`** |
| Color | `ashIntroTheme` | `white` · `market` · `pink` | **`white`** |

Also shipped: `ashIntroBar` (SL / success / TP / all), `ashIntroGate` (fingerprint / auto), `ashIdle` (on / pause). Apply matter/color/bar on **next launch**.

`INTRO_PALETTES` stay albedo. Lighting modulates them.

## What is already in code

- Shared Canvas 2D loop, `projectStorm` camera, ~5.6s assemble + hold
- Thin-plate lighting (`ASH_L` / `ASH_H`, spec 48, rim when face < 0.12)
- Flakes land on path-A homes; leftover ash can loop until ENTER
- Candle stems + SL/success/TP levels on A
- Path-drawn A on the boot canvas; sturdier SVG A in the coal orb
- `prefers-reduced-motion`: still A + wordmark, no storm
- Phone bake: laptop `?record=1` → `/api/intro-save`. Git ships `intro-flakes-white.webm` only; missing files fall back to live canvas

## If you must touch it

Keep Canvas 2D. Cap particles if the phone drops frames. Do not add Three.js / Chart.js / D3.

Ambient `#ambientAsh` reuses flake sprites. Settings already expose idle pause (WCAG 2.2.2). Do not make idle ash louder.

## Letter-as-material (research only — §1.8)

Do **not** ship 26 unique intros. Product boot stays **A / ash**. Emit / samara / extra letters are optional later, same engine.

## Agent check

- Can the user pick flakes *or* candles, and white *or* market *or* pink, independently?
- Does a flake go dim → flash → hairline as it tumbles (not a constant glow)?
- If you hide color, is the A still a drawn letter, not Georgia?
- Are you about to rebuild a function that already exists? Stop.
