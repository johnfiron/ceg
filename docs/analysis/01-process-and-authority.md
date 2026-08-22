# 1. Process and authority

Observed Friday 21 August 2026, 20:40 America/New_York.

## Job

Who may read the book, who may write it, and who may send a paper order.

## Source of truth

- ASH: [`app.py`](../../app.py) (`ENVIRONMENT`, `PROCESS_ROLE`, `WEB_READ_ONLY`, `broker_orders_enabled`, `place_broker_order`, `ah`, `db`), [`runner.py`](../../runner.py)
- Units: [`deploy/systemd/ash-web.service`](../../deploy/systemd/ash-web.service), [`deploy/systemd/ash-runner.service`](../../deploy/systemd/ash-runner.service)
- FamilyVault: loopback consumer only; it never holds Alpaca keys
- Live: `ash-web` / `ash-runner` environment, bind addresses, `/api/status`

## Invariants

- Orders stay on `https://paper-api.alpaca.markets/v2`. A changed `PAPER` origin fails closed.
- Production web cannot call `ah()`, cannot `place_broker_order`, and cannot mutate `/api/*`.
- Orders need JSON `broker_orders_enabled: true` **and** process env `CEG_ALLOW_BROKER_ORDERS` truthy **and** `PROCESS_ROLE` in `runner`/`test`.
- Importing `app.py` does not scan. Only `runner.py` runs `startup_reconcile` then `runner_loop`.
- One runner lock (`data/runner.lock` / `/var/lib/ash/runner.lock`).
- Web SQLite is `mode=ro` + `query_only`. Runner holds WAL.

## How it works now

Default role: development imports as `runner`; production imports as `web` unless `CEG_PROCESS_ROLE` is set. Production web sets `WEB_READ_ONLY`.

`place_broker_order` recovers a deterministic `client_order_id` if the HTTP response is lost. That is authority plus idempotency, not a second submit.

**Live**

| Fact | Value |
|---|---|
| `ash-web` | `ash-web` / `ash-readers`, role `web`, config `/etc/ash/config.web.json`, `CEG_ALLOW_BROKER_ORDERS=false`, bind `127.0.0.1:8765` |
| `ash-runner` | `ash-runner`, role `runner`, config `/etc/ash/config.production.json`, `CEG_ALLOW_BROKER_ORDERS=true` |
| Web config | no Alpaca/FRED keys, `broker_orders_enabled` false |
| Runner config | keys present, `keys_ok` true, `broker_orders_enabled` true |
| `/api/status` (web) | `configured` true, `paper_only` true, `broker_orders_enabled` false, `broker_runtime_armed` false |
| Public listen | Caddy `:80`/`:443` only. FamilyVault backend `127.0.0.1:3000`. ASH not on the public interface. |

The web status fields describe the **web process**. They do not say whether the runner is armed. Live, the runner is armed: both interlocks are true in the runner unit and production config. The checked-in [`ash-runner.service`](../../deploy/systemd/ash-runner.service) still says `CEG_ALLOW_BROKER_ORDERS=false`. The live unit was overridden so Monday can send paper orders.

`desk_configured()` is true for production web even without keys, so the monitor opens. That is read authority, not order authority.

## Tests and gaps

Covered: paper-only URL, dual interlocks (string `"true"` is not enough), web cannot arm or read `ah()`, import does not start the runner, production web opens without keys.

Not covered as a live assertion: the deployed runner unit’s `CEG_ALLOW_BROKER_ORDERS` versus the file in git. `/api/status` does not expose runner arming separately from web arming.

## Drift, gaps, next question

- **Drift:** git runner unit = interlock false; live runner unit = true. Next deploy that rewrites the unit file can disarm Monday unless the override is preserved.
- **Gap:** operators reading the monitor see `broker_orders_enabled: false` and may think the runner cannot fire.
- **Next question:** should status grow an explicit `runner_orders_armed` snapshot written by the runner, without giving the browser credentials?

Points at: [8](08-security-and-monitor.md) (why web has no keys), [9](09-deploy-backup-recovery.md) (unit install), [10](10-evidence-and-ops.md) (do not bounce the runner to “check” this).
