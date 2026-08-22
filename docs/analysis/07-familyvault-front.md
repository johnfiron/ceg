# 7. FamilyVault front

Observed Friday 21 August 2026, 20:40 America/New_York.

## Job

How a browser reaches the paper desk without ever holding Alpaca keys.

## Source of truth

- FamilyVault backend: [`tradingLab.ts`](../../.familyvault-work/backend/src/routes/tradingLab.ts), [`config.ts`](../../.familyvault-work/backend/src/config.ts), auth session / logout clearing `fv_ash_session`
- FamilyVault frontend: `VITE_TRADING_LAB_ENABLED`, Trading Lab route, [`e2e/live/desk-contract.spec.ts`](../../.familyvault-work/frontend/e2e/live/desk-contract.spec.ts)
- Caddy (live `/etc/caddy/Caddyfile`): `/ash` authorize then reverse_proxy to `127.0.0.1:8765`; mutations on `/ash` return 403
- ASH: `ASH_BASE`, `from=vault`, `desk_configured`

## Invariants

- `TRADING_LAB_BASE_URL` must be HTTP loopback (no userinfo, no extra path).
- Summary and session create/delete require authenticate + admin.
- ASH cookie `fv_ash_session` is httpOnly, Secure in production, SameSite=strict, path `/ash`, 12 hours, hashed at rest.
- Logout revokes the parent session and clears the ASH cookie.
- Browser never receives Alpaca credentials. Vault only GETs ASH `/api/status`, `/api/account`, `/api/trades` server-side.
- Session URL is `/ash/?from=vault` so ASH skips intro and locks Connect.

## How it works now

`sanitizeTradingLabSummary` publishes paper equity, `day_change`, `pnl_vs_start` vs $100,000, and splits Activity into `realized_pnl` (broker-backed closes) vs `unconfirmed_expired_*`. Recent trades include `exit_kind` and `broker_backed`.

Caddy: `@ashMutation` blocks non-GET on `/ash`. `handle_path /ash/*` asks FamilyVault `/api/trading-lab/authorize` then proxies to ASH. FamilyVault itself is the rest of the host (`@familyvault not path /ash`).

**Live:** Caddy 80/443 public. FamilyVault backend on `127.0.0.1:3000` (active). `familyvault-frontend.service` inactive — the SPA is static files, not that unit. `TRADING_LAB_PUBLIC_ORIGIN=https://brullpyre.duckdns.org`. ASH loopback 8765. Unauthenticated Playwright: login visible, Trading Lab in the compiled admin bundle, `/trading-lab` redirects to login, APIs 401/403, `/ash` cookie-gated, mutations blocked.

## Tests and gaps

Covered: loopback URL guard (unit), sanitize/KPI tests in `tradingLab.test.ts`, live desk-contract (5 passed on last run), ASH loopback spec (needs IAP tunnel to 8765; public IAP to `:8765` fails because ASH binds localhost).

Not covered in ASH CI: the Caddy authorize dance. Matrix rows for vault session live in [`security-verification-matrix.md`](../security-verification-matrix.md).

## Drift, gaps, next question

- **Hotfix history:** Trading Lab was once built without `VITE_TRADING_LAB_ENABLED` and the nav disappeared. Current live bundle contains Trading Lab. Next FamilyVault `origin/main` deploy must keep that flag.
- **KPI honesty:** after the 21 Aug repair, realized should sit near +503 and unconfirmed expire at −14. Re-check the live summary after a hard refresh if a service worker still holds an old chunk.
- **Next question:** should Trading Lab show the open QQQ mark next to `pnl_vs_start` so +504 equity and +503 book do not look like a fight?

Points at: [2](02-ledger-and-pnl.md), [6](06-desk-ui-and-identity.md), [8](08-security-and-monitor.md).
