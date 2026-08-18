# Prompt for the implementing agent

Copy everything below the line into a new agent chat.

---

Implement the ASH Terminal **title screen** (and only that, unless a tiny settings hook is required). Research is frozen. Do not re-research, do not invent a 26-letter alphabet, do not restyle the trading desk.

## Project

Local Flask paper-trading terminal at `/data/data/com.termux/files/home/projects/ash`. UI is one file: `static/index.html` (inline CSS + JS). Paper-only. Do not print or commit secrets from `config.json`.

**Server:** if you must restart, `ps` → kill the `python app.py` PID with `kill -TERM`, then `bash start.sh`. Never `pkill -f "python app.py"` (kills the agent). Exit 143 after SIGTERM is expected.

## Read first (in this order)

1. `docs/ui-rulebook.md` — especially §1.1–1.8, §7, §8
2. `.cursor/rules/ash-ui.mdc`
3. `.cursor/skills/ash-identity/SKILL.md`
4. `.cursor/skills/ash-intro/SKILL.md` — this is the how-to
5. Then only if you touch them: `ash-color`, `ash-type`

Do not load a new look from the internet. The book is the contract.

## What exists today

- Boot: `#introCanvas` / `makeStorm` / `stormFrame` / `drawCandle` / `drawBrandedA` (~523–642). 5.6s camera pull through unlit candlesticks, then Georgia `fillText('A')` + orbit ellipse.
- Ambient: `#ambientAsh` / `ashFrame` (~477–521). Flat `fillRect` flakes, loops forever (WCAG 2.2.2 — do not “fix” the session loop unless it is free while you reuse the flake drawer).
- Settings: one tab row `#introThemeTabs` — `market` / `white` / `pink` stored as `ashIntroTheme`. Default in code is still `market`.
- Masthead: `.brandOrb` CSS coal sphere + Times/Georgia `A`.
- Page cuts: `vaporizeTransition` — keep; that is the reverse of emit.

## Build this (A only)

One engine, product door = **letter A / material ash**. No B–Z. No Three.js, no Chart.js, no D3, no new font files unless you path-draw the A yourself.

### 1. Settings — two orthogonal axes

| Axis | `localStorage` | Values | New default |
|---|---|---|---|
| Matter | `ashIntroMatter` | `flakes` · `candles` | **`flakes`** |
| Color | `ashIntroTheme` | `white` · `market` · `pink` | **`white`** |

Two tab rows in Settings → Intro. Do not keep “GREEN / RED CANDLES” as one control. Apply on **next launch** (same as today). Optional third row later: flow `assemble` · `emit`; if you add it this pass, default `assemble`. Optional candle-bar row: SL · success · TP · all three; default **all three**.

### 2. Shared loop (Canvas 2D)

Keep `projectStorm` camera and ~5.6s timing. One `requestAnimationFrame` loop:

spawn → tumble + existing `chaos`/`gust`/`radial`/`lift` → project → light → draw (three depth buckets) → eye + A → `finishIntro()`.

`prefers-reduced-motion: reduce` (via `matchMedia`, not CSS alone): skip storm/tumble; still path-A + wordmark. After `finishIntro()`, stop the boot loop.

Budget ~800–1500 particles. If the phone drops frames, cap count — do not add WebGL in this pass.

### 3. Lighting (both matters)

Thin-plate model from `ash-intro`. Flicker = specular when N crosses L, plus rim when edge-on. Not `shadowBlur` on a flat rect.

```
L = normalize(-0.35, 0.55, 0.76)
V ≈ (0, 0, 1)
H = normalize(L + V)
face = |N·V|
diff = max(0, N·L)
spec = pow(max(0, N·H), 48)
rim  = face < 0.12
```

Draw foreshortened (width × `face`). Fill = albedo × (0.18 + 0.82·diff) + white/ember·spec. Bake 4–8 flake sprites once; `drawImage`. Never `ctx.filter` per particle.

Color is **albedo** only (`INTRO_PALETTES`). `white` = bone/ash. `market` = green/red. `pink` = Easter egg sparkles on top of lighting, not instead of it.

### 4. Flakes + assemble (identity default)

Ash-plate regime: tumble + specular flash. Particles start in the storm; in the last third of 5.6s they spring to homes sampled from the **path-A** (not Georgia `fillText`). Last ~1.2s **hold still**.

If you also ship `emit` this pass: homes start filled (or a still crown/tree), then shed into the storm — same points as vaporize, aimed at the mark. A is a double: fire-ash plates (assemble) and *Fraxinus* samara (emit can use autorotating keys). Do not build petal/droplet/sand yet.

### 5. Candles (option)

Same camera and light. **Stems** (the two diagonals of A) = short stacks of OHLC candles; up/down = albedo. **Crossbar** = a level, not a sideways candle: SL hairline under, short success body on the bar, TP/stop-gain hairline over (or all three). Overshoot the apex; no candle on the point.

### 6. Path-drawn A (replace Georgia)

Three paths: left stem, right stem, hairline crossbar that can read as one flake of ash. High-contrast serif, open counter. Title A naked on the void, lit like matter. Orb A = same letter, **sturdier** cuts at ~18px inside the existing coal `.brandOrb` (CSS or small canvas — no second logo). Wordmark stays tracked sans. No orbit ellipse. No script/neon/chart lockup.

### 7. Out of scope this pass

- Desk restyle (7px type, tables, `barChart` hue, Inter). Leave Home/Lab/charts alone.
- 26-letter dictionary, ABC names (beach/cherry), unique animation per letter.
- WebGL, new chart libraries, new display typeface for the app.
- Fixing ambient ash 2.2.2 pause unless you reuse the flake drawer and a pause is cheap. Do not make idle ash louder.

## Done when

- [ ] Settings: matter ⊥ color; defaults flakes + white; next-launch only
- [ ] Flake boot: plates tumble, dim → flash → hairline, then land as A and hold
- [ ] Candle boot: stems = candles, crossbar = SL/success/TP
- [ ] A is path-drawn (boot + orb), not system Georgia; still reads with color off
- [ ] `prefers-reduced-motion` shows a still A + wordmark
- [ ] No Three.js / Chart.js / D3; no secrets printed; desk CSS/JS untouched except settings + orb + intro/ambient drawers
- [ ] Identity check: color off + flakes paused, it still looks like ASH

If something fights 60fps on this phone, cap particles and say so. Do not start a second research pass.
