# Security implementation decisions

This repository implements the architecture in `docs/security_proto.md` together
with the FamilyVault repository that fronts ASH in production.

## Deployment boundary

- Caddy is the only public listener on ports 80 and 443.
- FamilyVault is the browser-facing BFF and owns authenticated browser sessions.
- `ash-web` is a loopback-only, read-only monitor behind FamilyVault
  authorization.
- `ash-runner` is a separate server authority with the only broker credentials
  and the only permission to submit paper orders.

The browser never receives Alpaca credentials. FamilyVault's browser JWT and
refresh-token lifecycle will be replaced by an opaque server-side BFF session.

## Autonomous paper-runner exception

Operation-bound browser signatures cannot authorize an unattended process while
the browser is locked or offline. ASH's autonomous paper runner therefore does
not use the user's client-vault signing authority. Its authority is constrained
instead by:

1. a permanently paper-only broker endpoint;
2. a runner-only credential boundary;
3. independent configuration and runtime order interlocks;
4. a single-runner host lock and deterministic order identifiers; and
5. reconciliation against broker state before evaluation.

Client-vault signatures are reserved for user-initiated exceptional operations
in FamilyVault. They must not be repurposed as a generic signing oracle.

## Production web invariant

`ash-web` is a monitor, not an operator surface. In production it must reject
all state-changing HTTP methods even when a same-host reverse proxy makes the
request appear to originate from loopback. Source IP is defense in depth, not
authorization.

No deployment step may grant the web process broker credentials or write access
to the ledger. Caddy and the Flask application both enforce the read-only
boundary so a mistake in either layer fails closed.
