# ASH UI

Visual work is gated by the rulebook, not by taste.

1. Read `docs/ui-rulebook.md` — identity first (§1.1–1.8), then tokens and drawers.
2. Load `docs/development/guides/ash-identity/guide.md` on visual work, then the group:
   - Type / fonts / numbers → `docs/development/guides/ash-type/guide.md`
   - Canvas or chart HTML → `docs/development/guides/ash-charts/guide.md`
   - Color, P&L, contrast → `docs/development/guides/ash-color/guide.md`
   - Spacing, touch, Home/phone structure → `docs/development/guides/ash-layout/guide.md`
   - Boot, flakes vs candles, title A, lighting → `docs/development/guides/ash-intro/guide.md`
3. Reuse `resize()` and existing drawers in `static/index.html`. Do not add Chart.js/D3 for a panel.
4. Nothing readable below 11 px. Touch 44×44. Color is never the only cue.
5. Do not implement a visual restyle unless the user asked. Title engine and desk type/phone contract are shipped.
6. Session, runner, orders, PDT, 0DTE, or Activity ledger → `docs/development/rules/ash-desk.md` and `docs/development/guides/ash-desk/guide.md`.
