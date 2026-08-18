---
name: ash-intro
description: ASH Terminal title-screen ceremony — flake vs candle matter, color palettes, fake-3D plate lighting, and the path-drawn serif A. Use when changing the boot storm, introCanvas, ambient ash, intro settings tabs, brand orb, drawBrandedA, or when adding 3D/lighting/flicker to the title card.
---

# ASH intro (title + mark)

Full contract: [docs/ui-rulebook.md](../../../docs/ui-rulebook.md) §1.6–1.7. Load `ash-identity` first. Do not restyle the desk.

Code today: `static/index.html` — `#introCanvas` / `stormFrame` / `drawCandle` / `drawBrandedA` (~523–642), `#ambientAsh` / `ashFrame` (~477–521), `.brandOrb` CSS, settings `#introThemeTabs` (~419), `setIntroTheme` (~1021).

## Two axes (orthogonal)

| Axis | `localStorage` | Values | Identity default |
|---|---|---|---|
| Matter | `ashIntroMatter` | `flakes` · `candles` | **`flakes`** (original) |
| Color | `ashIntroTheme` | `white` · `market` · `pink` | **`white`** |

Settings: **two tab rows**. Do not keep “GREEN / RED CANDLES” as one control. Apply on **next launch** (current theme contract).

`INTRO_PALETTES` stay albedo + wick + glow. Lighting modulates them; it does not replace them.

## Stack

Keep **Canvas 2D** + existing `projectStorm` camera. Budget ~800–1500 particles, 5.6s. No Three.js / WebGL unless a later pass proves Canvas cannot hold 60fps on phone.

Share one loop: spawn matter → tumble + advection → project → light → draw → eye + A → `finishIntro()`.

`prefers-reduced-motion`: skip storm/tumble; still path-A + wordmark. Boot-only motion is exempt from 2.2.2 while it is the only view; after `finishIntro()`, stop it.

## Fake 3D lighting (both matters)

Flake = **thin plate**. Flicker = specular when the tumbling normal crosses the light, plus a rim when edge-on. Not `shadowBlur` on a flat rect.

Per particle:

```
N  = rotate plate normal (tumble ax, ay)
V  ≈ (0, 0, 1) in camera space
L  = normalize(-0.35, 0.55, 0.76)   // one key, above-left
H  = normalize(L + V)
face = abs(dot(N, V))               // foreshorten
diff = max(0, dot(N, L))
spec = pow(max(0, dot(N, H)), 48)   // 32–80; rare flash
rim  = face < 0.12 ? 1 : 0
```

Draw: ellipse/quad with width × `face` (disk → hairline). Fill = albedo × (0.18 fill + 0.82 `diff`) + white/ember × `spec`. If `rim`, 1px stroke on the long edge.

- Bake 4–8 irregular flake sprites once; `drawImage`.
- Depth: three buckets (far / mid / near). Optional near canvas + CSS `blur(2px)` — never `ctx.filter` per particle.
- Candles: same L/V/H. Body = three box faces; wick = thin line. Up/down color is albedo. Pink sparkles stay costume-only.

Reuse existing `chaos` / `gust` / `radial` / `lift`. Add plate tumble; do not add a second particle system.

Ambient `#ambientAsh` can reuse the same flake drawer at lower count/opacity. Still needs pause after boot (WCAG 2.2.2) — that is identity, not this skill’s implement-now.

## Mark: a lettermark A

A single serif **A** is the logo. Not a monogram, not a candlestick icon.

Today is a placeholder: `fillText('A', Georgia 80)` + gradient + orbit ellipse; orb is CSS `Times`/`Georgia`. System fonts differ by OS — not ownable.

When implementing:

1. Draw the A as **three paths** (left stem, right stem, crossbar) so the same light can hit each plane.
2. High-contrast serif: thick stems, hairline crossbar. One distinctive cut: crossbar reads as a flake of ash.
3. Open counter — must hold at **18px** (orb) and **80px** (boot).
4. Title A is **naked** on the void. Orb A is the same letter inside the coal sphere (sturdier cuts).
5. Prefer assemble: matter collapses into the three strokes (physical, like `vaporizeTransition`). Do not only fade a `fillText`.
6. Wordmark stays tracked sans. Serif never enters the blotter.

Refuse: script A, neon outline, logo+chart lockup, swapping the whole UI to a display serif.

## Letter-as-material (research only — §1.8)

Do **not** ship 26 unique intros. One engine, four knobs: letter · matter · flow (`assemble`|`emit`) · material regime. Product boot stays **A / ash**.

- Flakes *land on* a stroke skeleton; candles *are* the stroke.
- Horizontals = SL / success body / TP (or all three), not sideways candles.
- Materials differ by **flight regime** (plate, samara, petal, droplet, grain) + sprite + albedo — not a new movie per letter.
- A is fire-ash plates **and** *Fraxinus* samara (emit = tree sheds). A is locked.
- ABC names (beach, cherry) are a picture-book. Prefer things that fall.
- Prototype A only before more glyphs.

## Agent check

- Can the user pick flakes *or* candles, and white *or* market *or* pink, independently?
- Does a flake go dim → flash → hairline as it tumbles (not a constant glow)?
- If you hide color, is the A still a drawn letter, not Georgia?
- If adding letters: same engine, new skeleton + material row — not a new title film?
