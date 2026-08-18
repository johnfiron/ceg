# ASH Terminal UI Rulebook

Canonical visual system for the paper-trading terminal. **Do not invent new type sizes, chart libraries, or palettes.** Skills under `.cursor/skills/ash-*` implement this book. Research sources are listed at the end.

This file is the contract. Skills are the how-to. Code lives in `static/index.html` (CSS at top, canvas helpers ~835–1090).

---

## 1. Intent

ASH is a **session research terminal on a phone first**, then tablet/LAN. Home must **explain** the live window. Charts support one decision. Lab can be denser.

Stack today: one Flask page, inline CSS, 2D canvas (no Chart.js/D3), HTML bars for progress/pareto. Keep that stack unless a later research pass replaces it.

Readable numbers and honest graphs sit **inside** the look the product already chose. Do not restyle toward Material, Linear-cyan, or Bloomberg neon. Do not strip the atmosphere to look “more professional.”

---

## 1.1 What this UI is trying to be

The name is the material. **Ash** is what is left after the fire: bone-white flakes on a void, not terminal-green hacker chrome and not a traffic-light trading floor.

The code already states this:

- True black canvas (`#000`), bone ink (`#f5f5f1`, `--ash #deded8`), hairline charcoal panels
- Ambient falling flakes (`ambientAsh`) — grey-white, never colored
- Boot: 2.5D **candlestick storm** that pulls into an eye, then a **serif A**, then tracked `ASH TERMINAL`
- Page changes **vaporize** into particles (text + edges + canvas samples) on a curl-noise wind — comment: “exact-origin chaotic-wind”
- Live candles are **ash / grey**, not green/red. Green/red is an optional intro costume (`market` / `white` / `pink`)
- Eyebrows are uppercase, tracked, heavy (`MARKET DATA · STRATEGIES`)
- Brand orb: metallic coal/pearl + Georgia/Times **A** — the only serif
- Floating pill dock, blur on **chrome only**
- CSS comment: “cinematic polish”

This is a **cinematic editorial terminal**: a film-title door, then a quiet midnight desk. Not a SaaS dashboard with a dark toggle. Not a Bloomberg clone.

The name of the look in 2025–26 writing is **dark editorial cinema** (charcoal/void, bone ink, one amber, serif as the mark). ASH is that language **plus a session desk**. Cinema sites are galleries. This product has to trade. The code already splits the jobs (see §1.2).

### Neighbors (steal grammar, not skins)

| Language | What to take | What to refuse |
|---|---|---|
| **Sequel / cinematic dark-stage** | Closest chrome: `#000`, linen `#f5f5f0` ≈ ASH `--text #f5f5f1`, 10–20px cards, **pill** controls | Gallery, not a blotter; whisper-light 300 body |
| **A24 / film-title cinema** | Void, type as the event, confidence through absence | Zero-radius magazine; no data desk |
| **Freshman / festival credits** | Tracked chapter-markers, one chromatic ration | Ultra-light italic wordmark as the whole UI |
| **Dark editorial cinema (2026)** | Three colors, no gradient-as-brand, serif ≠ Inter-as-display, **different language for different jobs** | Warm charcoal `#0c0a09` instead of ASH’s void; Fraunces on every heading |
| **iUSPC / midnight floor** | ~97% grey, tracked caps, one **ember** | Faint blue cast, perspective-grid hero |
| **TradeX institutional** | Red/green **only** for direction; chrome stays neutral | Density-as-brag; green-on-black clone |
| **Soft brutalism (2025)** | Heavy type contrast + usable pills | Raw brutalism (sharp corners, 9px mono as identity) |
| **Particle / title dissolve** | Dust, wind, physical cut (boot + `go()`) | Game-HUD glitch, holographic boot, particle type on every heading |

**Near-miss — do not become:** Sandclock / DeFi mint-terminal (green as brand signal). ASH green is direction, never chrome.

### Not this product

- Bloomberg / synthwave neon, cyan glow, glass cards as identity
- Material You tonal purple, `#121212` “dark mode”
- TradingView chrome, rainbow indicators
- Linear/Vercel mint-cyan accent (that is a different brand)
- Cyberpunk HUD, scanlines, “HACK THE MARKET”
- Soft skeuomorph gold “luxury fintech”

**Amber (`--amber`) is the ember** — VWAP, armed, stale, sample warning. It is the 3% chromatic ration. Blue is progress/tape. Violet is inspect/OUT. Green/red are **direction only**.

---

## 1.2 Atmosphere vs desk

Two layers, already in the DOM:

| Layer | Job | Rules |
|---|---|---|
| **Atmosphere** | Boot storm, ambient ash, vaporize | Pale flakes `rgba(230,230,224,…)`. No colored ash. `prefers-reduced-motion`: skip storm/vaporize, keep a still frame + wordmark. Do not paint atmosphere on top of plot pixels. |
| **Desk** | Panels, numbers, charts, explain | Quiet. Hairlines. Bone type. One chart. Color only for state. |

Cinema is the **entrance and the page cut**. The session is a **desk**. If atmosphere competes with a number, the number wins.

---

## 1.3 Type voice (identity, not just size)

The look is **stamped metadata + a large number**, not Inter-on-everything SaaS.

- **Eyebrow / chip / nav:** uppercase, tracked (+0.06 to +0.18em), heavy. This *is* the ASH caption voice (Control/iUSPC). Keep the voice when you raise size to the **11px floor** — identity is case + tracking + weight, not 7px.
- **Display number:** tight tracking, near-black weight, bone. Hero glow is a faint white radial, not a colored bloom.
- **Body / explain:** sentence case, tracking 0, readable. The terminal still has to talk.
- **Serif:** orb + boot **A** only. Never strategy cards, never table headers.

Two families: system sans (desk) + one serif (mark). Optional tabular/mono for digits only.

---

## 1.4 Motion grammar

Already implemented — extend, don’t replace:

1. **Boot (once):** camera pull through candle storm → eye → serif A → tracked wordmark → fade. 5–7s. Optional palettes are costumes; **classic white** is the identity default.
2. **Idle:** ash drift, slow, depth-sorted. Cap particle count on phones (already width-based).
3. **Navigate:** vaporize old page → turbulent wind → reassemble. Physical, not a 200ms fade.
4. **Desk:** almost still. Replay play and surface drag are tools, not brand.

No bounce, no springy SaaS, no colored particle bursts on tap.

---

## 1.5 What the live file already chose (do not reverse)

Read from `static/index.html`, not from a moodboard:

| Choice | In code | Meaning |
|---|---|---|
| Void, not warm charcoal | `--bg:#000` | After-fire black. Editorial-cinema articles prefer `#0c0a09`; ASH is colder on purpose. |
| Bone, not pure white | `--text:#f5f5f1`, `--ash:#deded8` | Sequel “Linen”. Warm ink on a cold void. |
| Ember ration | `--amber:#f1b94e` | VWAP / armed / stale. One spotlight, not a second brand. |
| Soft chrome | panel `20px`, dock `21px`, pills `999px` | Sequel/iOS prestige, **not** A24 zero-radius. |
| Blur on chrome only | topbar + `.bottomNav` | Desk glass. Plots stay unfrosted. |
| Monochrome tape | live `candles` ash/grey | Price is material, not a traffic light. |
| Costumes | `INTRO_PALETTES` market / white / pink | **white** is identity. Default in code is still `market` — a drift to fix later, not a new look. |
| Stamp voice | `.eyebrow` weight 950, tracking `.18em` | Identity is case + tracking + weight. Size can rise to 11px. |
| Serif lock | Georgia / Times on orb + boot A | Never blotter, never strategy cards. |
| Cinema comment | “cinematic polish”, “2.5D flying-candlestick storm”, “exact-origin chaotic-wind” | Atmosphere is authored, not leftover decoration. |

**Tension to keep, not average out:** cinema marketing uses 7px tracked meta; a phone desk cannot. Raise size, keep the stamp. Do not “clean” radii, ash, or the serif A to look more institutional.

---

## 1.6 How this *kind* of UI is done (2024–26 research)

ASH is already a hybrid. The neighbors that matter are not “dark mode dashboards.” They are **title-sequence cinema**, **editorial finance**, and **quiet instrument UIs**. The product fails when those three run at the same time on the same pixels.

### Three jobs, three languages

| Job | ASH already | How the genre does it well | Failure mode |
|---|---|---|---|
| **Ceremony** | Boot storm, serif A, vaporize | Bloomberg BQuant launch (Nov 2025) used particle worlds and motion studies to *introduce* a research terminal — then the desk is quiet. Game/film title cards (Territory, A24) end; they do not loop under the HUD. | Running the storm or colored particles during a session |
| **Masthead** | Tracked `ASH TERMINAL`, Georgia A, eyebrows | Editorial finance (FT, Linear’s rare Tiempos): serif is a **strike**, not a body face. Labels are stamped evidence (`SESSION TAPE · AND-GATE`). Display numbers tighten (Linear −0.02em at 40px) while captions open. | Serif on strategy cards; Inter-as-luxury everywhere |
| **Instrument** | Panels, chips, `line`/`candles`, keyboard | Linear / Raycast: no illustration in the product, accent on ~5% of a view, elevation by **hairline + one luminance step**, not drop-shadow theater. TradeX: red/green only for direction. | Rainbow indicators, Material purple, mint-as-brand |

Linear’s published system is useful as a **negative** and a **split**: they refuse gradients, hero video, and illustration *inside* the tool; speed *is* the brand. ASH should refuse the same *on the desk*, and keep cinema for the door. Do not copy Linear’s cool `#010102` blue-black or mint-cyan accent — that is a different material.

Raycast (dark-only tools): accent on ~5% of the view; blur ~20px (ASH dock is 19px — stay there); `saturate` on chrome, not on plots. They advise a surface ladder instead of pure black. **ASH keeps `#000` on purpose** (after-fire void). Elevation still comes from `#040404` panels and `#242424` hairlines, not from warming the void to `#0c0a09`.

### Bone on void (warm ink, cold stage)

2025–26 “warm never grey” systems (Yoshiki: lacquer / bone / gold, ~3% trigger color; Delightful: cream neutrals, no cold grey) match `--ash` / `--text` better than ice-white-on-#121212. Rules that transfer:

- ~95–97% bone + charcoal. Amber is the gold/ember line, **not a fill**.
- Green/red are Yoshiki’s “scarlet and moss”: triggers, not chrome.
- Price candles stay ash/grey so the tape is *material*, not a stoplight (already in `candles()`).

Do not “warm the background” to look more editorial. The void is the brand; warmth lives in the **ink**.

### Ceremony must end (WCAG + craft)

`ambientAsh` is a `requestAnimationFrame` loop of 140–360 flakes, `pointer-events: none`, under the desk, for the whole session. That is the same pattern as a looping stock ticker.

- **WCAG 2.2.2 Pause, Stop, Hide (Level A):** moving content that (1) starts by itself, (2) lasts **> 5 seconds**, and (3) sits **in parallel with other content** needs a pause/stop/hide control. Ambient ash meets all three. `prefers-reduced-motion` is **2.3.3 AAA** and **does not replace** 2.2.2 (FT’s 2024 VPAT treats 2.2.2 as a first-class A criterion; EAA enforcement 2025 treats AAA as best practice, not a substitute).
- Boot storm is OK without a pause **while it is the only content** (Understanding 2.2.2: a loader that is the whole view is exempt). After `finishIntro()`, it must not keep flying under Home.
- Craft: Linear/BQuant put spectacle at launch. NN/G Liquid Glass (Oct 2025): do not frost the thing you are reading. Ash behind a chart is atmosphere; ash **on** chart pixels is noise.

When implementing later: still-frame ash or hide after boot; a control to stop idle flakes; `matchMedia('(prefers-reduced-motion: reduce)')` around `ashFrame` / `stormFrame` / `vaporizeTransition` (CSS media queries do not stop `requestAnimationFrame`).

### Tracking is two voices, not one “luxury” setting

| Voice | Tracking | Genre |
|---|---|---|
| Eyebrow / chip / nav | **+0.06 to +0.18em**, uppercase | Festival credits, iUSPC stamps, terminal evidence |
| Display / clock / equity | **−0.02 to −0.04em** | Linear display, cinematic numerals |
| Body / explain | **0** | FT: “communicate, not pretty” — sentences must read |

Do not letter-space Body to feel more “ASH.” The stamp is the caption, not the paragraph.

### Glass and pills are chrome, not identity

Soft 20px cards + pill dock = Sequel / iOS prestige (already chosen). Identity is void + bone + ember + serif A + ash motion. If you remove the blur and the UI still reads as ASH, the identity held. If you remove the A, the flakes, and the tracked eyebrows, it is just another dark dashboard.

### Intro costumes (today)

Settings only switch **color** (`ashIntroTheme`: `market` / `white` / `pink`). Matter is hard-locked to flying candlesticks. Flakes were the original idea and still run as `#ambientAsh` under the desk — they are not a boot option. See §1.7.

---

## 1.7 Title screen: matter, light, mark

Two orthogonal settings. Do not fold color into the candle label.

| Axis | Keys | Identity default | Notes |
|---|---|---|---|
| **Matter** | `flakes` · `candles` | **`flakes`** | Original atmosphere. Candles are the trading costume. Same camera, same light. |
| **Color** | `white` · `market` · `pink` | **`white`** | `white` = bone/ash. `market` = green/red albedo. `pink` = Easter egg. |

Store separately: `ashIntroMatter`, `ashIntroTheme`. Settings UI: two tab rows, not “GREEN / RED CANDLES” as one blob. Next launch only (already the theme contract).

### Why flakes can look 3D (without Three.js)

A carbon flake is a **thin plate**, not a snowball. The “flicker” is physics: as the plate tumbles, its normal N sweeps past the light. Most frames are dim Lambert; a few frames are a **specular flash** when N lines up with the half-vector. Edge-on, the plate collapses to a bright hairline (rim). That is the look — not `shadowBlur` on a flat rect.

Ambient ash today: `fillRect` of `rgba(230,230,224,a)` with spin. Storm today: unlit candle bodies + optional glow. Both already have z / camera (`projectStorm`). Lighting is the missing layer.

**Stay on Canvas 2D for the boot.** ~800–1500 particles × 5.6s is inside the 1–3k Canvas budget. WebGL/Three.js is a later option if count or per-pixel lighting demands it — not required to look 3D. Do not add a chart library or a 3D engine for the title card.

### Shared light (flakes and candles)

One key light, slightly above-left and toward camera. Tiny fill so backs are not dead black.

Per particle each frame (reuse `projectStorm` for x,y,scale):

1. Tumble: Euler or two-axis spin (`ax, ay` + `ω`). Plate normal `N` from rotation. View `V` ≈ `(0,0,1)` in camera space after project.
2. Foreshorten: draw an ellipse/quad with one axis scaled by `|N·V|`. Face-on = disk; edge-on = line. This *is* the 3D.
3. Lambert: `diff = max(0, N·L)` × albedo (from the color axis).
4. Specular: `spec = pow(max(0, N·H), 32..80)` — short white (or ember) tick. High shininess = rare flicker, not a constant glow.
5. Rim: if `|N·V|` < ~0.12, add a thin bright stroke (catch light).
6. Depth: three buckets (far / mid / near) instead of a full sort. Optional: near layer on a second canvas with CSS `blur(2–3px)` — compositor blur, never `ctx.filter` per particle (cinematic-snow pattern).
7. Bake 4–8 irregular flake sprites once to an offscreen canvas; `drawImage` + tint. Do not `beginPath` a new polygon 1500× per frame.

Candles use the **same** L/V/H. Body = box with three fake face normals; wick = thin cylinder. Up/down color is **albedo**, not an extra bloom. Pink sparkles stay a costume on top of this, not a replacement for lighting.

Motion (already close): chaotic advection + gusts, not random walk. Fire-flake papers (IEEE Access 2021, PeerJ-CS 2025): flakes are light carbon plates driven by the surrounding flow. Keep the existing `chaos` / `gust` / `radial` / `lift`. Add tumble on the plate, not more emitters.

### The mark is a lettermark, not “Georgia A”

A single serif **A** is enough. ASH does not need a candlestick icon, phoenix, or chart glyph — those are costumes. The letter *is* the event (A24 pre-roll, film-title practice).

What it is **not**, yet: a designed mark. Today `drawBrandedA` is `fillText('A')` in Georgia 80px + a gradient + an orbit ellipse. The masthead orb is a coal sphere with a CSS `Times`/`Georgia` A. System serifs differ by OS. That is a placeholder.

| Application | Job | Rule |
|---|---|---|
| **Title A** | Cinema, naked on the void | Path-drawn letter (left stem, right stem, crossbar). Same lighting as matter so flakes/candles can collapse into the strokes. No container. |
| **Orb A** | 38px masthead / PWA | Same letter, **sturdier** cuts (Didone hairlines die at 18px). Orb is the container — metallic coal, not a second logo. |
| **Wordmark** | `ASH TERMINAL` tracked sans | Stays system sans. Serif never enters the blotter. |

Ownable details (draw these; do not pick a Google font and stop):

- High-contrast serif: thick stems, hairline crossbar (Didone / film-title). Crossbar can read as a single flake of ash — one distinctive cut, like IBM’s stripes.
- Open counter (the hole in the A) so it survives 18px.
- One weight, one stress angle, used in both boot and orb.
- Assemble, don’t fade: matter pulls into the three strokes (A24 geometry → letter). Matches `vaporizeTransition` (physical cut).

Refuse: script A, neon outline A, logo-plus-candlestick lockup, serif on `ASH TERMINAL`, a new display family for the whole UI.

Reduced motion: still path-A + wordmark, no storm/tumble loop (same as §1.6).

---

## 1.8 Letter-as-material (research — do not build 26 intros)

A variable monogram for every letter, each a *thing* (A=ash, B=beach, C=cherry…), with its own flake, candle, and special animation, is a **system**. It is not 26 products. 36 Days of Type is a gallery challenge: a new metaphor every day. Brands that last (A24, generative kits like Wolff Olins / Oi) keep **one grammar** and change parameters. If the default boot is a random letter, nobody learns ASH.

**Product door stays A / ash.** Other letters are a settings preview or Lab easter egg, not 26 default title sequences.

### One engine, four knobs

| Knob | Values | Identity |
|---|---|---|
| **Letter** | A–Z (skeleton paths) | **A** |
| **Matter** | `flakes` · `candles` | **flakes** |
| **Flow** | `assemble` (chaos → letter) · `emit` (letter/tree → chaos) | assemble for flakes; emit is the reverse you already have in `vaporizeTransition` |
| **Material** | flight regime + albedo + sprite (table below) | **A = ash** (locked) |

Color (`white` / `market` / `pink`) still tints albedo. Do not invent a new renderer per letter.

### Why this can work (sourced)

- **Particle → glyph is solved.** Offscreen `fillText` / path → `getImageData` → particles spring home (WIZ Particle Text, ICS WebGPU write-up, countless Canvas demos). ASH already does the reverse (`vaporizeTransition`). Assemble = home springs; emit = the same points leave along the wind.
- **Letters are skeletons, not pictures.** Type anatomy: stems (vertical/diagonal), bars/crossbars/arms (horizontal), bowls/spines (curves). One stroke list per glyph. Flakes *land on* the skeleton. Candles *are* the stroke.
- **Falling stuff actually looks different** because the flight regime changes, not because you write a new movie. Papers on falling plates (JFM, J. Mech.): steady / flutter / tumble / chaos. Ash *seeds* (*Fraxinus* samaras) autorotate on two axes (WJET 2017; McCutchen 1977) — a different motion from fire-ash plates. Petals flutter. Droplets are spheres (no tumble, optional splash). Sand is ballistic. That is how B/C/D differ without 26 shaders.
- **A is a double.** Fire residue (the product) **and** the ash tree’s winged seed. Emit mode can be a still tree/crown in the middle shedding samaras; assemble mode is bone plates landing into the A. Do not pick one and forget the other.
- **Candle horizontals map to the tape.** A Japanese candle is a *vertical* (body + wicks). An OHLC bar already has *horizontal* ticks (open left, close right). Chart levels are horizontals: stop-loss under, take-profit / stop-gain over, “in the money” as a mid success body. So: stems = stacked candles; bars = SL / success / TP, or all three as a sandwich. That is one rule for A, E, F, H, T — not a special case per letter.

### Why ABC naming is the trap

Ash / beach / cherry / droplet is a children’s alphabet. Beach is a place, not a fall. Q and X will be forced. Prefer **materials that flake, flow, or burn**, then attach a letter. A stays ash. Suggested regimes (names can change; the physics should not):

| Regime | Flight | Looks like | Example letters (not locked except A) |
|---|---|---|---|
| **Ash plate** | tumble + specular flash | fire residue, bone | **A** |
| **Samara** | autorotate (spin + precess) | *Fraxinus* / maple key | A emit, maybe M |
| **Petal** | flutter, slow, saturated | cherry, rose | C |
| **Droplet** | sphere, no tumble, splash | water, dew | D |
| **Grain** | ballistic, little spin | sand, beach | B |
| **Ember** | rise (heat), cools | live coal | optional costume |
| **Leaf / needle** | flutter or dart | oak, pine | later |

You do not need 26 regimes. Eight, reused, is a system. Twenty-six unique “special animations” is a year of title sequences (Kamil K’s 36 Days: a new C4D setup per letter, render-farm cost). Saul Bass: *symbolize and summarize* — one metaphor. Kyle Cooper: one psychology. A phone boot of 5–7s cannot carry a new film every launch.

### Candle construction (one grammar)

For each stroke in the skeleton:

- **Vertical / diagonal stem:** a short stack of OHLC candles, depth-sorted, same light as §1.7. Up/down from the color knob (or ash/grey in `white`).
- **Horizontal bar:** a level, not a tiny sideways candle (those read as noise). Choose, or layer: **SL** (hairline under), **success** (short in-the-money body on the bar), **TP / stop-gain** (hairline over). User option: SL · success · TP · all three.
- **Curve (O, S, C):** candles follow the tangent; skip SL/TP or use short level ticks at extrema only.
- **Apex (A, V, W):** two stems meet; do not put a candle on the point — overshoot the apex (triangular letters look short; type design overshoots the cap line).

### Flake construction (one grammar)

1. Sample the path-A (later, any letter) to home points — not Georgia `fillText` if we can path it.
2. `assemble`: particles start in the storm, advection as now, then lerp/spring to homes in the last third of the 5.6s. Last 1.2s **hold still** (motion-design rule: hold ≥ build).
3. `emit`: homes start occupied (or a still tree/crown), then shed into the storm. This is vaporize aimed at the mark.
4. Sprite + flight regime + albedo come from the material row. Lighting stays §1.7 (plate/samara/petal get N·L; droplets use spherical fake-normal).

### What we still do not know (honest)

- No one has shipped “stop-loss as the crossbar of an A” as a brand. The mapping is original; it may read as a chart mashed into a letter. Prototype **A only** before 26 skeletons.
- We have not measured Canvas 2D + lighting + 1500 homes on this phone. Budget is inferred (1–3k desktop; Android is harsher). Cap, then WebGL.
- Optical sizes: display A (80px, high contrast) vs orb A (18px, lower contrast, wider) — researched as a type rule, not drawn.
- A full 26-letter material dictionary is **not** researched. Do not assign Q/X/Z from the hip.
- Title-sequence craft (Bass / Cooper / NECSUS “title card” 10–15s): we have the *job* (symbolize), not a shot list or audio.

Implement order if asked: path-A + ash-plate assemble → add emit → add candle stems + SL/TP bars on A → one extra material (petal or droplet) as proof the table works → then more letters.

**Research freeze.** More reading will not answer the leftover questions. The next step is a prototype, not another source list. Do not research a 26-letter dictionary until A works.

---

## 2. Tokens (freeze these)

### Type roles (CSS px at 1× ≈ Apple pt)

| Role | Use | Size | Weight | Line-height | Tracking |
|---|---|---|---|---|---|
| Display | Equity, session clock | 32–40 | 700–800 | 1.1 | −0.03em |
| Title | Panel heads, explain headline | 16–20 | 650–700 | 1.25 | −0.02em |
| Body | Explain copy, settings, sentences | **15–16** | 400–500 | **1.45–1.55** | 0 |
| Meta | Secondary sentence | 13–14 | 400 | 1.45 | 0 |
| Label | KPI captions, chips, nav | **11–12** | 600 | 1.3 | +0.06em |
| Numeric | Prices, P&L, %, RVOL, scores | 14–18 | 600 | 1.2 | 0, tabular |

**Floor:** nothing a human must read is below **11 px**. Apple HIG iOS minimum is 11 pt; Material label-small is 11; body is 14–16. Current 7–9 px labels are out of contract.

**Family:** system stack (`-apple-system, Segoe UI, Roboto, system-ui`). Optional Inter **only if actually loaded**. Serif only on the brand orb. Two voices max: UI sans + tabular/mono for numbers.

**Units:** `rem` (or `clamp`) so WCAG 1.4.4 (200% zoom) and browser text size work. Do not hardcode new `px` except inside canvas after `resize()`.

**Numbers:** `font-variant-numeric: lining-nums tabular-nums`. Right-align. Fixed decimals. Slightly heavier than the label beside them.

### Space / touch / radius

| Token | Value |
|---|---|
| Grid | 4 / 8 / 12 / 16 / 24 / 40 |
| Touch | **44×44 CSS px** default (Apple). Floor 24×24 (WCAG 2.5.8 AA). Prefer 48 on Android. |
| Gap between targets | ≥ 8 px; ~12 with bezel, ~24 without |
| Card radius | 12–16 |
| Chip radius | 999 |
| Phone plot height | ≥ 200 px |
| Canvas series | ≥ 2 px at 1× |
| Canvas labels | ≥ 12 px (not 8 px) |

### Color roles (dark UI — recast, do not invert)

| Role | Job | Contrast |
|---|---|---|
| `--text` | Primary reading | ≥ 4.5:1 on `--bg` |
| `--text-mid` | Meta / secondary | ≥ 4.5:1 if < 18 px |
| `--text-lo` | Disabled / decorative | no reading |
| `--up` / `--down` | Direction | 3:1 vs bg **and** a non-color cue (`+`/`−`, position) |
| `--series-1` / `--series-2` | Chart series | 3:1 vs bg and vs each other |
| `--line` | Hairlines, grid | grid may be quiet; **data** marks may not |

Existing CSS vars (`--bg`, `--text`, `--muted`, `--green`, `--red`, `--amber`, `--blue`, `--violet`) stay the vocabulary. Tune values to pass contrast; do not add a fifth green.

Paul Tol high-contrast pair when two series must survive greyscale: blue `#004488`, yellow `#DDAA33`, red `#BB5566`.

---

## 3. Drawing stack — what exists and when to use it

All canvas plots go through `resize(canvas, fillBlack=true)` in `static/index.html`. It:

1. Sizes the bitmap to CSS box × `devicePixelRatio`
2. `setTransform(dpr, …)` so **draw in CSS pixels**
3. Clears; optionally fills `#030303`

Never set `canvas.width` yourself. Never draw in device pixels. After `resize()`, `w`/`h` are CSS pixels.

### Canvas functions (prefer extending these over new libraries)

| Function | Draws | Best for | Not for |
|---|---|---|---|
| `line(c, pts, key, color)` | One polyline, auto y-scale, 4 quiet grids, pad 34/11/8/30 | Equity, walk-forward, any **single series over time** | OHLC, categories, two series (no legend/axis) |
| `barChart(c, rows, key, label)` | Vertical bars from **midline zero**, green/red fill, 8 px labels | Signed P&L by ticker/strategy (few bars) | Time series, long names (use HTML bars), phone (labels collide) |
| `candles(c, arr, upto)` | OHLC wicks+bodies, **ash/grey** up/down (not green/red), optional prefix via `upto` | Price path, replay, MTF, workspace | P&L, counts, sparklines |
| `volumes(c, arr, upto)` | Volume columns, weak up/down tint, **no shared y with price** | Always **paired** under `candles` with the same `upto` | Standalone meaning |
| `spark(c, bars)` | Close-only polyline, no axes, `fillBlack=false` | Thumbnail next to a **number that already states the fact** | The only encoding of a move |
| `histChart(c, bins)` | Paired miss/fire columns + dashed ±1.25 ATR lines | MVR stretch distribution only | General histograms (fork it) |
| `tradeChart(c, pack)` | Candles + OR dashes + VWAP cone + VWAP line + IN/OUT markers | **One trade’s story** | Market overview, Home equity |
| `drawSurface(points)` | 3D scatter RSI×CP×RVOL, drag-rotate, color=P&L | Lab exploration **desktop** | Home, phone, any claim that needs a number |
| `drawXhair(c, frac)` | Dashed vertical at fraction; currently **mousemove** | Linked time across panes **if** a readout exists outside canvas | Hover-only on a phone (needs tap + labels) |

### HTML (DOM) encodings — often better on mobile

| Helper | Draws | Best for |
|---|---|---|
| `setupBar(s)` | CSS width bar, armed/hot classes | Distance-to-fire (AND-gate score) |
| `covBar(p)` / `covGridHTML` | Session completeness | Tape coverage, not price |
| `reasonBars(rows)` | Horizontal Pareto | Miss reasons, ranked counts |
| `.metric` / `.kpi` | Label + value rows | Numbers that must remain selectable text |
| `strategyCard` | Copy + stats | Models; keep `plain` as Body, stats as Numeric |

**Rule:** If the value is a **score, count, or percent in [0,1]**, use HTML bars. If it is a **price path or P&L path**, use canvas. If it is a **sentence**, use text, not a chart.

### Accessibility companions (every canvas)

Canvas is invisible to screen readers and has no selectable numbers.

1. Visible **title that states the question**
2. One-sentence takeaway or last value in the DOM
3. `aria-label` on the canvas **or** a summary node
4. On phone, a tiny table or metric list of the same series when the chart is the main object

Datawrapper model: alt text for the point, numbers for the rest.

---

## 4. Chart grammar (NN/g 3 Cs)

1. **Context** — one question per chart. Show a comparison (zero, VWAP, prior close, OR). Title is a sentence, not a filename.
2. **Clutter-free** — no extra grid glow, no 3D when 2D works, no six-pane grids on a 390 px screen. Direct-label the last point instead of a 7 px legend.
3. **Contrast** — one strong series; extras muted. Finding in accent; rest in ash.

### Job → encoding

| Job | Encoding | Function |
|---|---|---|
| Paper equity / realized P&L over time | Line + zero context in copy | `line` |
| Strategy / ticker P&L | Horizontal comparison | HTML `reasonBars`-style or `barChart` if ≤8 short IDs |
| Session / replay / MTF price | Candles | `candles` (+ `volumes` under replay) |
| Live tape thumbnail | Spark beside last price | `spark` + Numeric last |
| Setup proximity | Progress bar | `setupBar` |
| Miss mix | Pareto | `reasonBars` |
| Stretch vs fire | Histogram + threshold | `histChart` |
| This fill | Overlay story | `tradeChart` |
| CEG cloud | 3D scatter | `drawSurface` — Lab, not Home |

Avoid on phone: pie, stacked bars, 3D, 2×2/3×2 workspaces, 800 px tables.

---

## 5. Color and meaning

- **WCAG 1.4.3:** text 4.5:1 (3:1 if large).
- **WCAG 1.4.11:** chart marks, icons, focus rings 3:1 vs adjacent.
- **WCAG 1.4.1:** never hue alone. P&L and candles need `+`/`−`, words, or position. Today `barChart` is green/red only; `candles` already use ash/grey — prefer that pattern for price.
- Recalculate contrast in dark UI; do not assume light-theme palettes pass.
- Status (FIRE / DNT / STALE) uses **word + color**, not a 6 px dot alone.

---

## 6. Layout and touch

- **Phone (<850 px):** one column. One Display number, Body explain, one chart. KPIs 2-up max. No 4-up KPI row, no 3-up explain books, no 2-col strategy grid.
- **Thumb:** primary nav stays bottom; ≤5–6 destinations; labels ≥ 11 px; hit area 44.
- **Safe area:** `env(safe-area-inset-*)` on top bar and bottom nav (not only the boot overlay).
- **WCAG 2.5.1 / 2.5.7:** drag (surface rotate, replay scrub, xhair) needs a button/stepper alternative.
- **WCAG 2.4.11:** sticky nav must not cover the focused control or the thing just tapped.
- **WCAG 1.4.10:** no two-axis scroll to read. Tables become cards on phone (`min-width: 800px` is a known breach).
- Glass/blur on chrome only (NN/g 2025 Liquid Glass). Do not frost the plot.

Home order: **explain → the number → one supporting chart → closest-to-fire list → the rest in Lab.**

---

## 7. Balance rules (for any agent)

1. Read this book (especially §1.1–1.8 identity), then the skill for the group you are touching (`ash-identity`, `ash-intro`, `ash-type`, `ash-charts`, `ash-color`, `ash-layout`).
2. Reuse `resize` + existing drawers. Fork a drawer if the job is new; do not add a chart library for one panel.
3. If you change type size in CSS, change the **matching canvas `g.font`** (today 8 px / 11 px). They must not diverge.
4. If you add a series color, add a non-color cue and check 3:1.
5. Phone layout is the source of truth; desktop is progressive enhancement.
6. Do not ship a visual that cannot be stated in one sentence under the chart.

---

## 8. Current gaps (do not “fix” unless asked)

- Most UI type is 7–9 px; Inter is named but not loaded; no `rem` / tabular nums.
- Canvas axis labels are 8 px; `barChart` is hue-only; `drawXhair` is hover-only.
- Tables `min-width: 800px`; 6-item nav at 7 px; explain panel (~11–16 px) is the voice to standardize on.
- `ambientAsh` loops for the whole session with no pause control (WCAG 2.2.2 A). Intro default is `market` while identity is `white`.
- Boot matter is candles-only; flakes are ambient, not a title option. Neither is lit. `drawBrandedA` is system Georgia, not a path mark.
- Letter-as-material alphabet (§1.8) is researched as a system, not implemented. No 26-letter dictionary yet. SL-as-crossbar is untested.
- Remaining unknowns are prototype questions (fps, does the A read), not more articles. Research freeze until A is drawn.

---

## 9. Sources

### Identity / this look

- Sequel cinematic dark-stage (closest chrome: void + linen `#f5f5f0` + pills) — https://styles.refero.design/style/1bd3b2ba-9ad9-44ed-9130-03f9d94de821
- A24 cinematic editorial (Refero) — https://styles.refero.design/style/6afa22a6-bec8-47c3-b5ee-5d11d64902cb
- Freshman festival-credit dark — https://styles.refero.design/style/a6284fcd-fa69-4469-ac40-4239e5b84a39
- Framer prestige black — https://styles.refero.design/style/242db326-a6f3-482a-b12e-5e7f8af94981
- Dark editorial cinema (charcoal, amber, serif on display only; different language per job) — https://uxskill.laithjunaidy.com/blog/dark-editorial-cinema-design.html
- iUSPC midnight floor, ember 3% — https://styles.refero.design/style/46bca11b-6920-4d70-8dd7-c4e3dbc123c7
- TradeX: reject green-on-black; red/green for direction only — https://edwson.com/project-tradex-institutional.html
- Sandclock (near-miss: mint as brand — do not copy) — https://styles.refero.design/style/ccbb774f-d1a9-4cc6-b1be-31379ba0baf1
- Soft brutalism vs soft UI (2025) — https://rebrandy.pl/en/soft-ui-vs-brutalism-which-works-better-in-2025/
- Particle / dust type (atmosphere, not desk) — https://crazygl.com/hero/particle-typography
- Title-sequence boot as atmosphere (game/film door, then UI) — https://territorystudio.com/project/black-ops-7-intro/
- TypeUI “Power/Luxury” dark-first, type as decoration — https://www.typeui.sh/design-skills/luxury
- Linear brand: no illustration/hero-video in the product; accent as signal — https://welovedaily.net/article/linear-brand-system-speed-as-language
- Linear type (display tight, body 15/1.6, rare serif) — https://duply.ai/linear/design-md
- Raycast dark UI: ~5% accent, ~20px blur, surface ladder — https://seedflip.co/blog/raycast-design-system-dark-ui
- Bloomberg BQuant launch motion / particle worlds (Nov 2025) — https://www.behance.net/gallery/237883575/Bloomberg-BQuant-Case-Study
- Yoshiki: lacquer/bone/gold, ~3% trigger color, “warm never grey” — https://github.com/zinzaki/yoshiki
- Delightful: warm neo-brutalist neutrals, 44px mobile — https://github.com/kylesnav/delightful-design-system
- FT: communicate, not pretty; 2.2.2 in VPAT (Feb 2024) — https://medium.com/ft-product-technology/an-outbreak-of-accessibility-anti-patterns-e73577242ee8
- WCAG 2.2.2 Pause, Stop, Hide — https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html
- Reduced motion vs rAF (CSS does not stop JS loops) — https://modern-framework-accessibility.com/core-accessibility-principles-for-modern-frameworks/reduced-motion-and-animation-accessibility/respecting-prefers-reduced-motion-in-react-and-css/
- Canvas vs WebGL particle budget (1–3k Canvas; WebGL later) — https://simplified.media/guides/canvas-vs-webgl
- Cinematic snow: 3 depth layers, CSS blur on near canvas, no per-particle `ctx.filter` — https://github.com/lo-cafe/react-cinematic-snow
- Fire-flake = light carbon plate + chaotic advection (IEEE Access 2021) — https://doi.org/10.1109/ACCESS.2021.3054061
- Stochastic flake sparkle / microfacet flash — https://static.chaos.com/documents/assets/000/000/367/original/vray_stochastic_flakes.pdf
- Lettermark vs monogram; one letter can be enough — https://www.digitalpolo.com/blog/lettermark-vs-monogram/
- A24: custom Didone wordmark; pre-roll assembles geometry into letters — https://www.designyourway.net/blog/a24-logo/
- 36 Days of Type (gallery, not a product identity) — https://www.36daysoftype.com/
- Wolff Olins / Oi: one grammar, many instances — https://www.adweek.com/creativity/brands-amazing-new-logo-responds-voice-and-looks-different-each-person-170955/
- Particle text: offscreen glyph → home points — https://wiz.jock.pl/experiments/particle-text/
- Particle text (Canvas, 10k morph) — https://github.com/Axshatt/ParticleText
- ICS: scatter / wind / assemble from `getImageData` — https://ics.media/en/entry/221216/
- Letter skeleton: stem / bar / arm / bowl — https://pangrampangram.com/blogs/journal/anatomy-of-the-letterform
- Falling plates: steady / flutter / tumble — https://doi.org/10.1017/jmech.2015.47
- Ash samara autorotation (WJET 2017) — https://www.scirp.org/pdf/WJET_2017101108261275.pdf
- McCutchen 1977: ash and tulip samara spin — https://doi.org/10.1126/science.197.4304.691
- *Fraxinus* fruit = oarlike samara, not fire ash — https://mdc.mo.gov/discover-nature/field-guide/ashes
- Saul Bass: symbolize and summarize (Heritage 2025) — https://www.mdpi.com/2571-9408/8/8/329
- Title card as 10–15s brand fragment (NECSUS) — https://necsus-ejms.org/saul-bass-participatory-culture-opening-title-sequences-contemporary-tv-series/
- A overshoot / crossbar below center — https://www.oert.org/en/latin-alphabet-proportions/
- Optical size: small = wider, less contrast — https://justanotherfoundry.com/size-specific-adjustments-to-type-designs
- OHLC left/right ticks are already horizontals — https://www.cmegroup.com/education/courses/technical-analysis/chart-types-candlestick-line-bar

### Accessibility / platforms / charts

- Apple HIG Typography — https://developer.apple.com/design/human-interface-guidelines/typography (iOS default 17 pt, min 11 pt; Dynamic Type)
- WWDC24 Dynamic Type — https://developer.apple.com/videos/play/wwdc2024/10074/
- WWDC26 brand + custom fonts — https://developer.apple.com/videos/play/wwdc2026/251/
- Apple HIG Accessibility / Buttons — 44×44 pt targets
- Material 3 Typography — https://m3.material.io/styles/typography/overview (label 11, body 12–16)
- Android Material 3 Compose type scale — https://developer.android.com/develop/ui/compose/designsystems/material3
- WCAG 2.2 — https://www.w3.org/TR/WCAG22/
- WCAG 1.4.11 Non-text Contrast — https://www.w3.org/WAI/WCAG21/Understanding/non-text-contrast.html
- WCAG2Mobile (6 May 2025) — https://www.w3.org/TR/WCAG2Mobile-22/
- NN/G Choosing chart types — https://www.nngroup.com/articles/choosing-chart-types/
- NN/G Contrast in charts — https://www.nngroup.com/articles/contrast-charts/
- NN/G Liquid Glass (Oct 2025) — https://www.nngroup.com/articles/liquid-glass/
- Datawrapper accessible charts — https://www.datawrapper.de/academy/how-we-make-sure-our-charts-maps-and-tables-are-accessible
- Paul Tol colour schemes — https://personal.sron.nl/~pault/
- ColorBrewer — https://colorbrewer2.org
- Smashing Magazine fintech type (2023) — tabular lining figures, right-align numbers
