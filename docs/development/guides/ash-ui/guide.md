# ASH UI dispatcher

Not a restyle skill. Load the **group** skills so type, plots, color, and layout stay one system.

## Order of operations

1. Read [docs/ui-rulebook.md](../../../ui-rulebook.md) — identity first (§1.1–1.8), then tokens and drawers.
2. Load [ash-identity](../ash-identity/guide.md) on any visual pass (stop Bloomberg/Material drift).
3. Load only what you will touch:
   - Copy, font-size, numbers → [ash-type](../ash-type/guide.md)
   - Any `<canvas>` or bar/pareto → [ash-charts](../ash-charts/guide.md) (+ [drawing.md](../ash-charts/drawing.md) before editing a drawer)
   - Palettes, `.up`/`.down`, contrast → [ash-color](../ash-color/guide.md)
   - Grids, nav, touch, Home structure → [ash-layout](../ash-layout/guide.md)
   - Boot storm, intro matter/color, title A, orb → [ash-intro](../ash-intro/guide.md)
4. If the task is “make it look right on a phone,” load identity + **all four** groups. Identity, then layout, type, charts, color.
5. Reuse `resize()` and existing drawers. No new chart library.
6. Do not implement a visual pass unless the user asked — this repo is still in a research → skills → later-implementation sequence.

## Balance checks (before finishing a UI change)

- [ ] No readable text < 11px (CSS **and** `g.font`)
- [ ] Numeric values tabular + signed
- [ ] Hue is not the only up/down cue
- [ ] Chart has a DOM title + last value
- [ ] Phone: one column, main plot ≥ 200px, tap ≥ 44px
- [ ] Same token used in CSS and canvas for a given meaning
- [ ] Still reads as ASH with color off and flakes paused (identity, not costume)
