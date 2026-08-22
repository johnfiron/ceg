# 8. Security and monitor boundary

Observed Friday 21 August 2026, 20:40 America/New_York.

## Job

What must fail closed so a browser, a proxy, or a mistaken unit file cannot trade or leak runner secrets.

## Source of truth

- Intent: [`docs/security_proto.md`](../security_proto.md), [`docs/security-implementation.md`](../security-implementation.md), [`docs/security-verification-matrix.md`](../security-verification-matrix.md)
- ASH: `_enforce_web_boundary`, `ah`, `WEB_READ_ONLY`, `db()` query_only, export 403, guest LAN, security headers
- FamilyVault: BFF session, CSRF / Fetch Metadata, operation signing (user vault ops — not the paper runner)
- Live: Caddy-only 80/443, ASH IP allow localhost, web ReadOnlyPaths, IAP SSH

## Invariants

- Caddy is the only public listener. ASH web is loopback, read-only, no broker credentials.
- Production web rejects all state-changing HTTP methods, including traffic that looks like loopback from a same-host proxy. Source IP is defense in depth, not authorization.
- Export of the full database is unavailable on the production monitor.
- Browser never receives Alpaca keys. Runner credentials stay in root-managed `/etc/ash/config.production.json`, mode not world-readable, unreadable by `ash-web`.
- Autonomous paper runner does **not** use FamilyVault client-vault signatures. Its authority is paper endpoint + runner role + dual interlocks + host lock + deterministic ids + reconcile.
- Guest LAN (development): GET Home/Activity allowed; mutating `/api/*` is local-only unless `allow_lan_orders`.

## How it works now

`_enforce_web_boundary`: production web → export 403; non-GET 403; comments are not a production-web exception. Development guests get 403 on mutations unless local or `allow_lan_orders`.

`ash-web` sandbox: `ProtectSystem=strict`, `ReadOnlyPaths=/var/lib/ash` plus web config, write only `arena.db-shm`, `IPAddressAllow=localhost`, `IPAddressDeny=any`. Runner may reach Alpaca.

Caddy also 403s `/ash` mutations before the proxy. Two layers; a mistake in either should fail closed.

**Live:** public 80/443 = Caddy. 8765 and 3000 are 127.0.0.1. Web config has no keys. Runner config has keys. IAP SSH as documented in the recovery runbook.

## Tests and gaps

Covered: production web read-only behind loopback proxy; export blocked; web cannot `ah()` or place orders; guest cannot POST intro save; baseline security headers; desk not cached persistently; matrix rows for ASH production web and paper interlocks.

FamilyVault: session opacity, CSRF, admin≠auth, lock wipes, operation challenges — see the matrix. Those tests live in the vault repo, not `tests/test_safety.py`.

Not covered here: a continuous external probe that Caddy still 403s POST `/ash/api/config` from the public origin (Playwright live contract did this on the last vault pass).

## Drift, gaps, next question

- **Autonomous exception** is documented and correct: you cannot require a browser signature for 15:45 while the phone is locked. Keep that exception narrow.
- **CSP** on ASH Flask is Report-Only; Caddy sets an enforcing CSP on `/ash`. Drift is acceptable if Caddy stays in front.
- **Next question:** confirm `config.web.json` cannot grow Alpaca keys “for convenience.” `desk_configured()` exists so it never needs them.

Points at: [1](01-process-and-authority.md), [7](07-familyvault-front.md), [9](09-deploy-backup-recovery.md).
