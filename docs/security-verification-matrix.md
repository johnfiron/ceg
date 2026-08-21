# Security verification matrix

This matrix maps the staged controls in `docs/security_proto.md` to executable
evidence in the ASH and FamilyVault repositories. “Pre-deploy gate” means the
control is implemented locally but cannot truthfully be marked as observed in
production until the security branches are reviewed, merged, deployed, and
probed. No test may silently downgrade a failed cryptographic or authorization
dependency into ordinary session authorization.

## Automated authorization and session checks

| Invariant | Evidence | Result |
|---|---|---|
| Browser identity uses an opaque, hashed, expiring, revocable session | `backend/tests/authLoginRoundtrip.test.ts`, `sessionSecurity.test.ts` | Pass |
| Session load rejects revoked, idle-expired, absolute-expired, and stale-version rows | `sessionSecurity.test.ts` SQL-boundary assertion | Pass |
| Mutations require same origin, same-site Fetch Metadata, JSON content type, and session CSRF proof | `sessionSecurity.test.ts`; `requestSecurity.ts` global hook | Pass |
| Authentication does not grant admin authority | `sessionSecurity.test.ts` requireAdmin cases; `authorizationBoundaries.test.ts` family/trading wiring | Pass |
| Production ASH web rejects all mutation methods and export, including loopback proxy traffic | `tests/test_safety.py` production boundary tests | Pass |
| ASH web cannot read runner credentials or arm broker orders | `test_production_web_role_cannot_arm_or_read_broker_credentials` | Pass |
| Autonomous orders remain paper-only and require independent config/runtime interlocks | broker endpoint/interlock tests in `test_safety.py` | Pass |
| Logout revokes the current BFF session and child ASH sessions | `authorizationBoundaries.test.ts` logout SQL assertion | Pass |
| Password/recovery/member-removal operations require current step-up | `sessionSecurity.test.ts` expiry tests and protected route prehandlers | Pass |

## Cryptographic authorization, lock, replay, and race checks

| Invariant | Evidence | Result |
|---|---|---|
| Operational P-256 private key is imported non-extractable | `frontend/src/crypto/__tests__/operationSigning.test.ts` | Pass |
| Application has no generic arbitrary-byte signing method | `frontend/src/stores/__tests__/auth.test.ts` public-API assertion | Pass |
| Signature binds version, operation, subject, resource, exact parameters, nonce, audience, issue time, and expiry | backend/client canonical challenge implementation | Pass |
| Modified parameters or wrong audience fail verification | `backend/tests/operationAuthorization.test.ts` | Pass |
| Wrong session, user, family, operation, or resource cannot consume a challenge | bound atomic SQL assertion in `operationAuthorization.test.ts` | Pass |
| Expired challenge cannot be consumed | `expires_at > now()` atomic SQL assertion and client expiry test | Pass |
| Two concurrent requests consume a challenge at most once | concurrent consumption test | Pass |
| Invalid parameter submission burns rather than preserves the challenge | burn-on-mismatch test | Pass |
| Lock wipes byte key material while retaining identity | `frontend/src/stores/__tests__/auth.test.ts` | Pass |
| In-flight/stale authority fails after lock | authority-generation race test | Pass |
| Signing fails after lock and before a new unlock | expired/post-lock signing test | Pass |
| Deterministic ASH order IDs and pending-row locks prevent duplicate autonomous submission | retry/pending tests in `test_safety.py` | Pass |

## XSS, cache, and delivery checks

| Invariant | Evidence | Result |
|---|---|---|
| FamilyVault scripts are self-only and Trusted Types is enforced | `backend/tests/serverHeaders.test.ts`; Caddy/Helmet policies | Pass locally |
| Inline style permission is limited to style attributes, not stylesheet/script execution | header test | Pass locally |
| API/session/key responses are `no-store` | global backend header test; ASH header test | Pass |
| Service worker excludes APIs and ASH authenticated navigation | `frontend/src/sw/__tests__/navigationDenylist.test.ts` | Pass |
| FamilyVault logout clears vault state and ASH tab cache | `sensitiveCache.test.ts`; AppShell wiring assertion | Pass |
| ASH validates authorization before restoring cache, uses tab-only storage, and expires it after five minutes | `test_authenticated_desk_is_not_cached_persistently` | Pass |
| Stored journal markup is escaped | `test_journal_escapes_stored_debrief_html` | Pass |
| ASH enforced CSP can remove inline script/event permission | Report-only policy is shipped first; production violation collection and extraction remain a pre-deploy gate | Not yet enforceable |

## Deployment and recovery checks

| Invariant | Evidence | Result |
|---|---|---|
| Public management ingress is absent; SSH is IAP-only | live GCloud firewall inventory after approved hardening | Pass 2026-08-20 |
| Public ingress is limited to Caddy 80/443 tags | live firewall inventory | Pass 2026-08-20 |
| VM service account lacks Secret Manager authority | live IAM inventory | Pass 2026-08-20 |
| Daily disk snapshots retain 14 days | live `familyvault-daily` policy attached to boot disk | Pass 2026-08-20 |
| Python and npm builds are manifest-locked | exact `requirements.txt`; `npm ci` deployment gates | Pass locally |
| FamilyVault deployment requires encrypted off-host backup before migration | `deploy/deploy-main.sh` | Shell/build gate pass |
| ASH backup is consistent, integrity-checked, encrypted, uploaded, and remotely size-checked | `deploy/backup-offsite.sh` | Shell gate pass; production configuration pending deploy |
| FamilyVault database/config backup fails if off-host upload is unavailable | `deploy/backup.sh` | Shell gate pass; production observation pending deploy |
| SQLite and Postgres/config restore drills are reproducible and refuse unsafe targets | both `verify-restore` scripts | Shell gate pass; quarterly operator drill pending |
| Unauthenticated production denial and headers survive Caddy | `deploy/smoke-security.sh` | Pre-deploy gate |
| Caddy configuration validates with the production binary | Run `caddy validate --config /etc/caddy/Caddyfile` on host | Pre-deploy gate |

## Required release gate

Before merging/deploying these branches:

1. Review all commits in both repositories and take an on-demand restore point.
2. Configure ASH’s age recipient and isolated rclone remote.
3. Deploy outside the ASH trading window.
4. Run migrations, builds, tests, `systemd-analyze verify`, and production Caddy validation.
5. Run `deploy/smoke-security.sh` and authenticated lock/logout/session probes.
6. Collect ASH report-only CSP violations. Extract inline scripts/handlers and
   enforce the strict policy only after required first-party behavior is clean.
7. Download fresh off-host backups and complete both offline restore drills.
