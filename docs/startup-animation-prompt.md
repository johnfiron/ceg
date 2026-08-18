# Directed prompt: ASH startup animation

Copy everything below the line into a **new agent chat** in this repo. The agent needs no prior context.

---

You are implementing the **ASH Terminal startup animation** (title door only). You have never seen this project. Do not invent a new product look. Do not restyle the trading desk. Do not research a 26-letter alphabet. Do not add Three.js, WebGL, Chart.js, or D3 to the phone boot. Laptop `?record=1` bake may stay Canvas 2D for this pass.

Replace the current ~5.6s “camera already in a storm → snap/spring into A” shot list. Keep useful pieces (path-A geometry, plate lighting, `#introCanvas`, fingerprint ENTER, `needs-keys` gate). Rewrite the **choreography**.

## What this product is

ASH is a **phone-first Flask paper-trading terminal**. One HTML file drives the whole UI. Cinema is the **door**; the session is a **quiet desk**.

Identity: **bone flakes on a true-black void, a path-drawn serif A, then tracked `ASH TERMINAL`.** Not Bloomberg, Material, Linear mint, or hacker green.

- Canvas `#000` · ink `#f5f5f1` / `#deded8` · ember `#f1b94e` (3%, not a fill)
- Green/red = intro **costume albedo** only

## Where to work

| Path | Why |
|---|---|
| `static/index.html` | Only UI file. Intro: `#introCanvas`, `#introVideo`, `#bootOverlay`, `#introPrint`. Title JS: `// ---------- title engine`. |
| `docs/ui-rulebook.md` | Identity §1.1–1.8. Do not follow the old 5.6s assemble timing. |
| `.cursor/skills/ash-identity/SKILL.md` | Steal / refuse |
| `.cursor/skills/ash-intro/SKILL.md` | Lighting / path-A / palettes |
| `app.py` | Serves `/` and webm bake. No strategy changes. |

Never print or commit `config.json` / `data/`.

Run: `bash start_wsl.sh` → http://127.0.0.1:8765  
Restart: `kill -TERM` the `python app.py` PID. Never `pkill -f "python app.py"`. Hard-refresh after edits.

## Gate (do not break)

Until Connect passes Alpaca + FRED, `html`/`body` have `needs-keys`: hide `#terminal`, `#nav`, `.topbar .actions`; no page scroll. Intro must land on `#setup`, not Home/Activity.

## Scene (this is the movie)

Phases. Do not skip ahead except as noted for **return visits**.

### 0. Persistence

`localStorage` e.g. `ashIntroSeenGround=1` after the floor is fully settled **once**.

- **First open:** play the fall from empty (phase 1).
- **Later opens:** skip phase 1. Start with flakes **already evenly on the ground plane** (phase 2). Same draft / orbit / fill after that.

Reduced motion: still path-A + wordmark, no fall/storm. Then the usual door.

### 1. First open — fall from nothing

Screen starts **empty**. Flakes spawn at the **top**, not already in a storm.

- Slow fall, wafting: randomized drift, not straight down, not a particle fountain.
- Intensity **picks up** (spawn rate / count ramps). Start from nothing.
- They **land** on a plane at the **bottom of the screen**. Evenly distributed across that ground. Landing is physical: slow, settle, lie down — same rule as the letter later.
- After they are on the ground you do **not** need per-flake physics until the draft picks them up. A ground **pool** (positions + rest pose) is enough. Do not keep simulating a pile if it is still.

### 2. Upward draft (bottom-left, then it climbs)

A draft **slowly** starts lifting flakes from the **bottom left**, on a windy chaotic path **up and to the right**.

- Flake **speed does not change** as the scene “loads.” What changes is the **initial angle / origin of the draft band** as it climbs the screen (future: climb rate can track real load; for now a slow authored climb).
- Off-screen wrap is **not** an instant teleport to the other edge. The motion is **around a ring/cylinder**:
  - Travel left → right on the near side.
  - Continue around the far side (you will see this once the camera pulls back).
  - Climb **left-to-right, then right-to-left**, with a **delay** so it still feels like going around the circle, not popping.
- As the band climbs, more of the ground pool is recruited into the wind.

### 3. Camera out — oval that becomes a circle

Once the circulation **fills the height** (the draft “is there”):

- Start **zooming the camera out** (fake 3D; reuse/adapt `projectStorm`).
- Paths slowly stop being a climbing ribbon and become a **chaotic squished circle (oval)** that **morphs into a circle**.
- You see flakes on the **far side** of the ring as the camera reveals depth. Far-side appearance is the **same wrap journey**, now visible — not a second spawn.

### 4. Per-flake waves (required architecture)

Do **not** drive everyone with one global sine.

Each flake has its **own** wave / oscillator (phase, frequency, amplitude, maybe a coupling weight). That is so later you can make them **interact** (wake, avoid, clump) by coupling those waves — not by a special-case “collision engine” this pass.

This pass: independent waves + a **shared wind field** (draft + ring). Optional light coupling (neighbor phase pull) if it stays cheap. Structure the state so interaction is a later multiplier on the same waves.

### 5. Storm, then fill the A — land, do not bullet

When it is a **clustered storm** (circle of flakes):

- Randomly choose flakes from the storm — **only as many as needed to fill the letter**, not more.
- Those flakes **change path** and **fall into place** in the **middle** (the A).
- **No outline, ghost, or path-A draw until the fill is complete.** The letter is only the flakes that have landed. After the last home is occupied, you may reveal the path-A (or hold on the flake-A only — flake-A must already read).
- **15 seconds** to complete the fill (authored; not 5.6s).
- Remaining storm flakes keep orbiting; they do not all dive in.

**Landing (non-negotiable):** they must **fall into place**, like settling onto the ground in phase 1. They must **not**:

- lerp in a straight streak (“bulleted”)
- teleport onto a pixel
- overshoot like a missile and stick
- scale/fade onto a pre-drawn A

Do: leave the ring on a curve, lose speed, last body-lengths are a **drop and settle** onto the stroke (tumble → lie flat on the plate). Ease is heavy at the end. Homes come from sampling the path-A offscreen; the A itself stays **invisible** until fill is done.

Then: tracked `ASH TERMINAL` (`#bootText`). Fingerprint: leftover storm loops until ENTER. Auto: timed. Then `finishIntro`. **Do not rewrite ENTER** in this job — that door is a separate brief: [docs/enter-cut-prompt.md](enter-cut-prompt.md).

## Look (keep)

Plate lighting (Lambert + rare spec + rim). Sprites baked. Albedo from `ashIntroTheme`. Matter `flakes` is this movie; `candles` can wait or share the same phases with candle sprites — **flakes first**. Path-A geometry already in `pathAPolys` / `drawPathA` — use it for **homes**, not as a visible guide during fill.

Settings matter ⊥ color stay. Defaults flakes + white.

## Out of scope

Desk restyle, 26 letters, WebGL/Three.js on the phone, live orders, secrets, louder idle ash under Home.

## Done when

- [ ] First open: empty → top spawn → wafting fall → even ground; later opens skip to ground
- [ ] Draft from bottom-left, climbs; wrap is around a ring with delay, not instant
- [ ] Camera out; oval → circle; far side is the same travelers
- [ ] Per-flake wave state (interaction-ready)
- [ ] Random subset fills the A in **15s**, exact home count, **no outline until done**
- [ ] Fill flakes **settle/fall into place** — not bullets, not snaps
- [ ] `needs-keys` still hides the desk; no Three.js/Chart.js/D3 on the boot path
