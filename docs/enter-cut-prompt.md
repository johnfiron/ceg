# Directed prompt: ASH ENTER cut

Copy everything below the line into a **new agent chat** in this repo. The agent needs no prior context.

The **startup movie is already shipped.** Do not rewrite fall / draft / orbit / 15s A fill. This job is only the **ENTER door** after the A is assembled and the leftover storm is looping.

---

You are implementing the **ASH Terminal ENTER cut** (title → open screen only). You have never seen this project. Do not invent a new product look. Do not restyle the trading desk. Do not rewrite the startup movie. Do not add Three.js, WebGL, Chart.js, or D3 to the phone boot. Do not bake a new webm for this pass.

Replace `explodeIntroToDesk` in `static/index.html`. Keep the movie, fingerprint ENTER, `needs-keys` gate, plate lighting, and `ensureAssembledStorm()` (webm viewers still reconstruct A+ring, then play this live cut).

## What this product is

ASH is a **phone-first Flask paper-trading terminal**. One HTML file drives the whole UI. Cinema is the **door**; the session is a **quiet desk**.

Identity: **bone flakes on a true-black void, a path-drawn serif A, then tracked `ASH TERMINAL`.** Not Bloomberg, Material, Linear mint, or hacker green.

- Canvas `#000` · ink `#f5f5f1` / `#deded8` · ember `#f1b94e` (3%, not a fill)
- Green/red = intro **costume albedo** only

## Where to work

| Path | Why |
|---|---|
| `static/index.html` | Only UI file. ENTER lives in `finishIntro` → `explodeIntroToDesk`. Title JS: `// ---------- title engine`. |
| `docs/startup-animation-prompt.md` | The movie **before** ENTER. Do not redo it. |
| `docs/ui-rulebook.md` | Identity. |
| `.cursor/skills/ash-identity/SKILL.md` | Steal / refuse |
| `.cursor/skills/ash-intro/SKILL.md` | Lighting / palettes / path-A |
| `app.py` | Serves `/`. No strategy changes. |

Never print or commit `config.json` / `data/`.

Run: `bash start_wsl.sh` → http://127.0.0.1:8765  
Restart: `kill -TERM` the `python app.py` PID. Never `pkill -f "python app.py"`. Hard-refresh after edits.

## Gate (do not break)

Until Connect passes Alpaca + FRED, `html`/`body` have `needs-keys`: hide `#terminal`, `#nav`, `.topbar .actions`; no page scroll. ENTER must land on `#setup`, not Home/Activity.

`RECORD` / `prefers-reduced-motion`: keep the existing fade in `finishIntro`. Do not run the particle cut.

## What is wrong today

`explodeIntroToDesk` fights the movie:

1. ~670ms tear toward a **random** `tearAnchor` (implode family)
2. ~880ms **magnetic snap** of `fxCanvas` rects onto sampled UI
3. Destination HTML fades in at `q≈0.22` while flakes are still flying

That is bullets plus a sting on top of a pre-drawn page. Do **not** keep the snap term. Do **not** implode to a point. Do **not** switch the ENTER matter to vaporize rectangles.

Leave `vaporizeTransition` (in-desk page cuts) alone.

## What ENTER must feel like

A **mixture of three spines, one sequence** (~3.2s authored, not another 15s movie):

1. **Through the circle** — camera commits **through** the leftover ring. The ring becomes a tunnel. The open screen is the far side of the cylinder.
2. **Finger is the wind** — gust origin is `#introPrint` (bottom-center). Capture its rect **before** hiding it. Not a random tear anchor.
3. **A goes cold** — letter cohesion dies. Flakes shed from the **bottom of the A first** (highest `_y`). They tumble and fall. They do not lerp, rocket, or fade off the glyph.

**Non-negotiable extra:** everything on the open screen is **formed by those flakes**. Do not fade HTML in on top of a particle sting. The destination chrome is flake homes. HTML stays opacity 0 until the last assigned flake has lain flat, then a short 1:1 swap so inputs work.

## Shot list

All three spines overlap. Do not play them as three cuts.

### 0–0.15s — Press

- Read `#introPrint` center. That is the gust origin.
- Hide the print. Kill path-A ghost and `#bootOverlay` immediately so nothing pre-drawn remains.

### 0–0.9s — Through + gust

Title camera in `stormCam` currently dollies **out** (`dist` 455→740). ENTER **inverts** that: `dist` falls toward ~90–140 so the leftover ring fills the frame as a tunnel. Slight `fov` up is OK.

Wind is from the fingerprint, mostly **up and through**. Per-flake `wavePhase` / `waveAmp` stay live — flight is not a straight streak.

### 0.2–1.1s — Cold (overlap)

A flakes (`p.land`) lose home hold. Recruit from the bottom of the letter first. They start to fall while the camera carries them through. Ring flakes keep orbiting; the dolly turns that orbit into edge streaks / a tunnel, not a second spawn.

### 0.9–3.0s — Form the open screen

Same `storm` plates. Draw on `#introCanvas` with `drawLitFlakeOn` / `paintStormXY`. **Not** `fxCanvas` vaporize rects.

Each flake that has a dest home uses the **existing landing grammar** from `layoutParticle` `state==='landing'`:

- leave on a **bezier**
- lose speed
- last ~30% is a **drop** from a stage point above the home
- tumble → lie flat (`restRot` / `lieAx`)
- ease heavy at the end

Do **not**: lerp in a streak, teleport, missile-overshoot, magnetic `snap`, or scale/fade onto pre-drawn HTML.

### 2.85–3.2s — Handoff

HTML opacity 0 until homes are occupied. Then canvas out / HTML in. Then `revealDesk()` as today (hide intro, start ambient, keep the keys gate).

## Everything formed by ash

The open screen is whatever ENTER is allowed to reveal:

- `needs-keys`: `#setup` + `.topbar` brand (actions stay hidden)
- unlocked: `#home` + `.topbar` + `#nav`

Prepare dest (`hidden` removed, `opacity:0`, two rAFs) so `getClientRects()` is valid.

Sample **more than today’s 1450-rect sting**:

- Reuse `collectTextParticles` for every visible glyph (eyebrow, `h2`, `.sub`, labels, button text, brand)
- Add an ENTER-only box sampler (do not change page vaporize): also `input`, `label`, `.setup`, `.eyebrow`, `.brand`
- Inputs = **border flakes only**. Empty field interiors stay black.
- Oversample until dest homes ≥ storm count when possible. Leftover ring becomes hairlines and frames — it does not vanish.

Assignment (story, not a random dump):

- `p.land` (the A) → center type first (eyebrow / title / sub)
- ring → borders, inputs, topbar, nav

Extra flakes with no dest pixel: sparse rest on the void (same settle). Not a second orbit under the form.

## Code shape

Rewrite `explodeIntroToDesk` as a small enter state machine on existing `storm` bodies.

- New states **local to this cut**: `shed` → `through` → `landing` → `landed`
- Do **not** overload the 15s fill timer
- Reuse `bezier`, `smootherstep`, `projectStorm`
- Add an enter-cam (`dist` down) rather than reusing title `stormCam`
- `ensureAssembledStorm()` stays for the video path
- After the cut, existing `revealDesk()` in `finishIntro`

## Look (keep)

Plate lighting (Lambert + rare spec + rim). Sprites baked. Albedo from `ashIntroTheme`. Matter `flakes` first. Path-A geometry is homes-only during the movie; during ENTER do not draw a ghost A.

## Out of scope

Startup movie rewrite, desk restyle, 26 letters, WebGL/Three.js on the phone, live orders, secrets, louder idle ash under Home, new webm bake, changes to `vaporizeTransition`.

## Done when

- [ ] Fingerprint (or auto) ENTER plays this cut; movie before it is unchanged
- [ ] Gust comes from `#introPrint`; camera goes **through** the ring; A sheds from the bottom and goes cold
- [ ] Setup (or Home) **appears as landed flakes**, not a fade of HTML over a sting
- [ ] Landing is bezier → drop → lie flat — no snap, no bullets, no implode-to-a-point
- [ ] `needs-keys` still lands on `#setup` only
- [ ] Reduced motion / record still fade; no Three.js/Chart.js/D3 on the boot path
