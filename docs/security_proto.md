\# Trading Lab Authentication, BFF, and Vault Security Architecture



\## Recommended Architecture



Use a \*\*Backend-for-Frontend (BFF)\*\* as the primary authentication architecture.



OAuth access and refresh tokens should never be exposed to the browser.



The security model should deliberately separate:



1\. \*\*Identity / authenticated session\*\*

2\. \*\*API authority\*\*

3\. \*\*Cryptographic vault authority\*\*

4\. \*\*Step-up authorization for exceptional operations\*\*



The core rule is:



> \*\*The browser session proves identity to the BFF. The BFF owns OAuth/API

> authority. The locally decrypted vault key owns cryptographic authority.

> Lock destroys cryptographic authority without ending the authenticated

> session. Logout revokes server-side session continuity and destroys all

> client authority. Sensitive operations require both server authorization

> and operation-specific cryptographic authorization.\*\*



\---



\# 1. High-Level Architecture



&#x20;                   ┌─────────────────────┐

&#x20;                   │       Browser       │

&#x20;                   │                     │

&#x20;                   │ opaque HttpOnly     │

&#x20;                   │ session cookie      │

&#x20;                   │                     │

&#x20;                   │ encrypted vault     │

&#x20;                   │        │            │

&#x20;                   │   master password   │

&#x20;                   │        │            │

&#x20;                   │        ▼            │

&#x20;                   │ non-extractable     │

&#x20;                   │ CryptoKey           │

&#x20;                   └───────┬─────────────┘

&#x20;                           │

&#x20;                operation-bound signature

&#x20;                           │

&#x20;                           ▼

&#x20;                 ┌───────────────────┐

&#x20;                 │        BFF        │

&#x20;                 │                   │

&#x20;                 │ session auth      │

&#x20;                 │ authorization     │

&#x20;                 │ CSRF enforcement  │

&#x20;                 │ replay protection │

&#x20;                 │ OAuth token store │

&#x20;                 │ refresh rotation  │

&#x20;                 │ step-up state     │

&#x20;                 └────────┬──────────┘

&#x20;                          │

&#x20;                   Bearer / DPoP

&#x20;                          │

&#x20;                          ▼

&#x20;                 ┌───────────────────┐

&#x20;                 │   Trading APIs    │

&#x20;                 └───────────────────┘



\---



\# 2. Browser Must Not Own OAuth Tokens



With a BFF, remove OAuth-token lifecycle management from React entirely.



The browser should NOT contain:



\- OAuth access tokens

\- OAuth refresh tokens

\- access-token expiration parsing

\- `ensureAccessToken()`

\- browser-side token refresh timers

\- BroadcastChannel token synchronization

\- `navigator.locks` OAuth refresh coordination

\- Service Worker OAuth token storage

\- browser-generated `Authorization: Bearer ...` headers

\- OAuth tokens in `localStorage`

\- OAuth tokens in `sessionStorage`



Instead:



Browser

&#x20;   │

&#x20;   │ authenticated request + session cookie

&#x20;   ▼

BFF

&#x20;   │

&#x20;   │ Authorization: Bearer <access-token>

&#x20;   ▼

Trading API



This removes an entire category of browser token-exfiltration and

multi-tab refresh-race problems.



\---



\# 3. Browser Session



The browser receives only a high-entropy opaque session identifier.



Example:



Set-Cookie:

\_\_Host-session=<cryptographically-random-session-id>;

Path=/;

Secure;

HttpOnly;

SameSite=Strict



Do not place OAuth tokens in this cookie.



Prefer an opaque identifier backed by server-side session state.



Conceptually:



session {

&#x20;   sessionId,

&#x20;   userId,



&#x20;   createdAt,

&#x20;   lastActivityAt,

&#x20;   absoluteExpiresAt,



&#x20;   authenticationLevel,



&#x20;   revoked,



&#x20;   oauthAccessToken,

&#x20;   oauthRefreshState,



&#x20;   securityState

}



The browser's cookie proves possession of the BFF session.



It does NOT itself grant cryptographic vault authority.



\---



\# 4. Application Security States



| State | BFF Session | Vault Key | Authority |

|---|---|---|---|

| Logged Out | No | No | Public |

| Authenticated + Locked | Yes | No | Read / low-risk APIs |

| Authenticated + Unlocked | Yes | Yes | Cryptographically authorized operations |

| Step-Up Authorized | Yes | Yes | Exceptional security-sensitive operations |



Authentication and vault unlock MUST remain separate concepts.



Authentication answers:



> Who is this user?



Unlock answers:



> May this browser process currently exercise this user's cryptographic

> authority?



Step-up authorization answers:



> Has the user sufficiently re-established intent/authentication for this

> unusually sensitive operation?



\---



\# 5. Boot Behavior



Application startup becomes:



PAGE LOAD

&#x20;   │

&#x20;   ▼

GET /bff/session

&#x20;   │

&#x20;   ├── valid session

&#x20;   │       │

&#x20;   │       ▼

&#x20;   │   AUTHENTICATED

&#x20;   │      LOCKED

&#x20;   │

&#x20;   └── invalid session

&#x20;           │

&#x20;           ▼

&#x20;       LOGGED OUT



A React reload MUST NOT require the master password simply to restore the

authenticated application.



The master password is required only when cryptographic vault authority is

needed.



\---



\# 6. Vault Unlock



The private vault should remain encrypted while locked.



Conceptually:



master password

&#x20;     │

&#x20;     ▼

memory-hard KDF

&#x20;     │

&#x20;     ▼

derived key / KEK

&#x20;     │

&#x20;     ▼

decrypt wrapped vault material

&#x20;     │

&#x20;     ▼

non-extractable CryptoKey

&#x20;     │

&#x20;     ▼

restricted signing authority



Where browser support and the cryptographic architecture permit it, import or

generate the operational private key as:



&#x20;   extractable: false



using WebCrypto.



This makes ordinary key export unavailable.



However:



> Non-extractable does NOT mean XSS cannot use the key.



Malicious same-origin JavaScript may potentially cause an accessible key to

perform operations even if it cannot export its bytes.



Therefore non-extractability is defense-in-depth, not the primary XSS

boundary.



\---



\# 7. Never Expose a Generic Signing Oracle



Avoid exposing:



vault.sign(arbitraryBytes)



to the rest of the application.



Prefer narrowly defined capabilities:



authorizeOrder(...)

authorizeWithdrawal(...)

authorizeCredentialRotation(...)

authorizeSecretExport(...)



The signing component should construct and canonicalize the actual

cryptographic payload internally.



This reduces the possibility of compromised application code repurposing the

vault as an arbitrary signing oracle.



\---



\# 8. Operation-Bound Cryptographic Authorization



Sensitive operations should require authorization tied to the EXACT operation.



For example, an order authorization should cryptographically bind:



version

operation

user/account

transaction ID

server challenge / nonce

instrument

side

quantity

order type

price / limit parameters

destination where applicable

issued-at timestamp

expiration

audience

relevant security context



Conceptually:



signature = Sign(

&#x20;   vaultPrivateKey,

&#x20;   CanonicalEncode({

&#x20;       version,

&#x20;       operation,

&#x20;       account,

&#x20;       transactionId,

&#x20;       challenge,

&#x20;       parameters,

&#x20;       issuedAt,

&#x20;       expiresAt,

&#x20;       audience

&#x20;   })

)



The server verifies the exact same canonical representation.



A signature authorizing:



BUY 5 XYZ @ $100



must not be reusable to authorize:



BUY 500 XYZ @ MARKET



or another endpoint, account, transaction, or destination.



\---



\# 9. Sensitive Trading Flow



Browser                         BFF

&#x20;  │                             │

&#x20;  │ POST /prepare-order         │

&#x20;  ├────────────────────────────>│

&#x20;  │                             │

&#x20;  │                             ├─ authorize session

&#x20;  │                             ├─ validate order

&#x20;  │                             └─ generate challenge

&#x20;  │

&#x20;  │ transactionId

&#x20;  │ nonce

&#x20;  │ expiration

&#x20;  │ canonical context

&#x20;  │<────────────────────────────┤

&#x20;  │

&#x20;  │ vault authorizes exact

&#x20;  │ transaction

&#x20;  │

&#x20;  │ POST /execute-order

&#x20;  │ order

&#x20;  │ transactionId

&#x20;  │ signature

&#x20;  ├────────────────────────────>│

&#x20;  │                             │

&#x20;  │                             ├─ authenticate session

&#x20;  │                             ├─ authorize account

&#x20;  │                             ├─ verify challenge

&#x20;  │                             ├─ verify expiration

&#x20;  │                             ├─ verify parameters

&#x20;  │                             ├─ verify signature

&#x20;  │                             ├─ reject replay

&#x20;  │                             ├─ atomically consume nonce

&#x20;  │                             └─ execute downstream

&#x20;  │

&#x20;  │ result

&#x20;  │<────────────────────────────┤



Challenges should be:



\- unpredictable

\- short-lived

\- transaction-bound

\- audience-bound

\- single-use



Nonce consumption should be atomic.



\---



\# 10. Lock Must Have Real Security Meaning



Lock must do substantially more than change UI state.



LOCK

&#x20;│

&#x20;├─ release decrypted CryptoKey references

&#x20;├─ release derived encryption keys

&#x20;├─ destroy pending signing capabilities

&#x20;├─ cancel pending sensitive transactions

&#x20;├─ discard unlock-specific state

&#x20;└─ invalidate any temporary client-side cryptographic authority



BUT:



&#x20;   keep authenticated BFF session



After Lock:



session cookie       = YES

authenticated        = YES

portfolio read       = YES



private vault key    = NO

signing authority    = NO

trade authorization  = NO



Therefore:



> A valid BFF session alone MUST NOT be sufficient to perform an operation

> classified as requiring vault authorization.



JavaScript cannot guarantee physical RAM zeroization because of garbage

collection, browser internals, copies, and runtime optimization.



Do not claim guaranteed RAM erasure.



Instead, design the system so that dropping references and invalidating

capabilities makes previously unlocked authority unusable.



\---



\# 11. Logout



Logout is different from Lock.



LOCK:



&#x20;   destroy cryptographic authority

&#x20;   retain identity/session



LOGOUT:



&#x20;   destroy cryptographic authority

&#x20;   revoke server session

&#x20;   revoke/invalidate appropriate refresh state

&#x20;   expire browser session cookie

&#x20;   destroy remaining client session state



Logout must occur server-side.



Deleting browser state alone is insufficient.



\---



\# 12. OAuth Token Management Moves Entirely to the BFF



The BFF owns:



\- OAuth access token

\- refresh token

\- refresh-token family

\- token expiration

\- token rotation

\- replay detection

\- synchronization

\- revocation



Conceptually:



browser request

&#x20;     │

&#x20;     ▼

BFF receives session

&#x20;     │

&#x20;     ▼

access token usable?

&#x20;     │

&#x20;  ┌──┴───┐

&#x20;  │      │

&#x20; YES     NO / expiring

&#x20;  │      │

&#x20;  │      ▼

&#x20;  │   refresh

&#x20;  │      │

&#x20;  │   ┌──┴────┐

&#x20;  │ success   invalid refresh

&#x20;  │   │          │

&#x20;  │   ▼          ▼

&#x20;  │ continue   revoke session

&#x20;  │

&#x20;  ▼

downstream API



OAuth refresh synchronization now occurs in controlled server infrastructure

rather than across arbitrary browser tabs.



\---



\# 13. Refresh Rotation



Refresh rotation must remain server-authoritative.



The server should maintain enough state to identify token families and detect

reuse.



Conceptually:



family A

&#x20;  │

&#x20;  ├── generation 1

&#x20;  │       ↓

&#x20;  ├── generation 2

&#x20;  │       ↓

&#x20;  ├── generation 3

&#x20;  │       ↓

&#x20;  └── ...



Unexpected reuse of an invalidated generation can indicate token theft.



Race behavior must be explicitly designed and tested.



Do not depend on browser synchronization for security correctness.



\---



\# 14. Distinguish Authentication Failure From Infrastructure Failure



Do NOT treat every refresh failure as logout.



Network timeout:



&#x20;   authentication state UNKNOWN

&#x20;   do not immediately destroy session



OAuth server 5xx:



&#x20;   authentication state UNKNOWN

&#x20;   retry according to bounded policy



Invalid/revoked refresh credential:



&#x20;   authentication state DEAD

&#x20;   revoke BFF session

&#x20;   require authentication



This prevents temporary infrastructure failures from becoming destructive

authentication events.



\---



\# 15. Separate Expiration Domains



Use independent lifetimes for:



1\. OAuth access authority

2\. authenticated browser session

3\. vault unlock authority



Conceptually:



OAuth access token:

&#x20;   short



BFF session:

&#x20;   inactivity timeout

&#x20;   +

&#x20;   absolute maximum lifetime



Vault unlock:

&#x20;   shorter inactivity timeout



This allows:



AUTHENTICATED + LOCKED



to remain convenient while ensuring unattended cryptographic authority

disappears substantially sooner.



Repeated activity must not create an immortal session.



Use both:



&#x20;   inactivity expiration

&#x20;   +

&#x20;   absolute expiration



where appropriate.



\---



\# 16. Security Events and Session Revocation



Security-relevant account changes should trigger explicit session policy.



Examples:



password change

MFA change

account recovery

credential replacement

suspicious authentication

logout

logout-all-devices

administrative revocation



The server should be capable of:



revoke(session)



revoke(refreshFamily)



revokeAllSessions(user)



depending on the event.



\---



\# 17. Active Session Management



Treat authenticated devices/sessions as explicit server-side entities.



Users should ideally be able to inspect active sessions and revoke individual

ones.



Useful metadata can include:



session creation time

last activity

approximate client/device description

authentication level

revocation state



Avoid unnecessarily invasive device fingerprinting.



Session identifiers themselves must remain secret.



\---



\# 18. CSRF Protection



Moving authentication behind a cookie-authenticated BFF makes CSRF protection

critical.



For mutation endpoints enforce multiple layers.



For example:



SameSite=Strict

\+

Origin validation

\+

Fetch Metadata validation

\+

non-simple mutation requests

\+

explicit CSRF token where appropriate



Mutations should use appropriate methods:



POST

PUT

PATCH

DELETE



not GET.



Conceptually:



if request mutates state:



&#x20;   require authenticated session



&#x20;   require expected Origin



&#x20;   validate Sec-Fetch-Site / Fetch Metadata policy



&#x20;   require accepted Content-Type



&#x20;   validate CSRF proof where required



&#x20;   then perform authorization



SameSite should be treated as defense-in-depth rather than the only CSRF

control.



\---



\# 19. Server-Side Authorization



Authentication MUST NOT imply authorization.



A valid BFF session means:



&#x20;   identity established



It does NOT mean:



&#x20;   operation permitted



Every protected operation should evaluate something equivalent to:



authenticated

AND

subject authorized

AND

resource belongs to / is accessible by subject

AND

operation permitted

AND

security state sufficient

AND

vault authorization present when required

AND

step-up requirement satisfied when required

AND

transaction constraints valid



Authorization enforcement must occur on trusted server-side components.



Never rely on hidden buttons, React routes, or client state as authorization.



\---



\# 20. Step-Up Authorization



Some operations should require more than merely having an unlocked vault.



Examples:



export private key

change master password

disable MFA

replace recovery credentials

add/change withdrawal destination

change security policy

register a new cryptographic key

large/high-risk transfer



Conceptually:



READ PORTFOLIO

&#x20;   BFF session



NORMAL SENSITIVE TRADE

&#x20;   BFF session

&#x20;   +

&#x20;   vault authorization



EXCEPTIONAL SECURITY OPERATION

&#x20;   BFF session

&#x20;   +

&#x20;   vault authorization

&#x20;   +

&#x20;   recent step-up authentication



Step-up authorization should itself expire.



\---



\# 21. DPoP



DPoP may still be useful between:



BFF → downstream OAuth resource server



if supported by the authorization infrastructure.



However:



DPoP key

&#x20;   MUST NOT equal

vault/trading key



They represent different security domains.



DPoP establishes:



&#x20;   this OAuth client possesses the key associated with this token



Vault authorization establishes:



&#x20;   this user's unlocked cryptographic authority approved this exact

&#x20;   sensitive operation



Keep those responsibilities separate.



\---



\# 22. XSS Is Now One of the Dominant Browser Threats



The BFF dramatically reduces OAuth-token theft from browser JavaScript.



It does NOT eliminate XSS.



Malicious same-origin JavaScript could potentially:



\- make authenticated BFF requests

\- manipulate displayed transaction information

\- attempt to invoke vault functionality while unlocked

\- alter transaction parameters before authorization

\- interfere with user intent

\- access other JavaScript-visible application data



Therefore the browser security boundary must receive serious attention.



\---



\# 23. Strict Content Security Policy



Treat CSP as an architectural requirement rather than something added after

development.



Prefer a nonce/hash-based Strict CSP rather than a large host allowlist.



Target architecture should move toward something similar to:



default-src 'none';

script-src 'nonce-<random>' 'strict-dynamic';

object-src 'none';

base-uri 'none';

frame-ancestors 'none';



with explicit:



connect-src

img-src

style-src

font-src



rules according to actual application requirements.



Avoid:



'unsafe-inline'

'unsafe-eval'



wherever technically possible.



CSP should initially be deployed/report-tested carefully so required

application functionality is understood before strict enforcement.



\---



\# 24. Trusted Types



Use Trusted Types where browser support and application architecture permit.



Target:



Content-Security-Policy:

&#x20;   require-trusted-types-for 'script'



Dangerous DOM sinks should not accept arbitrary strings.



Create a minimal number of audited Trusted Types policies.



Do NOT create a permissive policy that simply returns every supplied string,

because that largely defeats the control.



\---



\# 25. Third-Party JavaScript



Minimize third-party JavaScript on security-critical origins.



Avoid placing things such as:



\- tag managers

\- advertising scripts

\- arbitrary analytics

\- customer-support widgets

\- unnecessary CDN JavaScript

\- marketing experimentation frameworks



inside the vault's trust boundary.



Every third-party script executing with the application's origin potentially

expands the security boundary.



For a sufficiently high-value vault, consider origin isolation:



app.example.com

&#x20;   normal application functionality



vault.example.com

&#x20;   minimal application

&#x20;   minimal dependencies

&#x20;   no third-party JavaScript

&#x20;   strict CSP

&#x20;   Trusted Types

&#x20;   cryptographic functionality



This is optional because it increases engineering complexity, but it can

create a meaningful browser security boundary.



\---



\# 26. Dependency Security



Dependency compromise is especially important for an application capable of

financial or cryptographic operations.



Maintain:



\- locked dependency versions

\- minimal dependency count

\- automated vulnerability scanning

\- dependency update review

\- reproducible builds where practical

\- software composition analysis

\- provenance/signature verification where supported

\- review of build-time dependencies

\- review of transitive dependencies

\- protection of CI/CD credentials

\- protected release branches

\- controlled deployment authority



Do not focus exclusively on runtime dependencies.



A compromised build pipeline can bypass many runtime browser defenses.



\---



\# 27. JWT Verification



Where JWTs exist between trusted backend components, decoding is NOT

verification.



Resource servers must strictly verify:



\- cryptographic signature

\- expected issuer

\- expected audience

\- expiration

\- not-before where used

\- allowed algorithms

\- appropriate key

\- relevant authorization claims



Allowed algorithms must be configured by trusted server policy.



Do not dynamically trust an algorithm merely because an attacker-controlled

JWT header requested it.



JWT validity also does NOT replace authorization.



\---



\# 28. Logging and Security Telemetry



Log security-relevant events such as:



authentication success/failure

session creation

session revocation

refresh-token reuse detection

step-up authentication

vault-sensitive transaction authorization

rejected signatures

expired transaction challenges

replayed challenges

authorization failures

security-setting changes



Do NOT log:



master passwords

private keys

raw cryptographic secrets

refresh tokens

access tokens

sensitive CSRF secrets

full secret-bearing headers



Logs themselves become sensitive security assets and require access control,

retention policies, and integrity protection.



\---



\# 29. Fail Closed



Security-sensitive paths should fail closed.



Examples:



signature verification unavailable

&#x20;   → reject sensitive operation



authorization service unavailable

&#x20;   → reject sensitive operation



transaction challenge expired

&#x20;   → reject



unknown authorization state

&#x20;   → reject



vault signature malformed

&#x20;   → reject



Do not silently downgrade:



vault-authorized operation

&#x20;       ↓

ordinary authenticated operation



because a security subsystem is unavailable.



\---



\# 30. Concurrency and Atomicity



Financial operations require more than authentication security.



The server must handle:



\- duplicate submissions

\- retries

\- race conditions

\- concurrent requests

\- challenge replay

\- transaction replay

\- idempotency



Where appropriate use:



transaction ID

\+

idempotency key

\+

single-use challenge

\+

atomic server-side state transition



For example:



UNUSED CHALLENGE

&#x20;     │

&#x20;     │ valid authorization

&#x20;     ▼

atomically mark CONSUMED

&#x20;     │

&#x20;     ▼

execute operation



Two concurrent requests must not both successfully consume the same

authorization.



\---



\# 31. Security Verification Is Part of the Architecture



Once these boundaries exist, adding more authentication mechanisms provides

diminishing returns.



The highest-return security work shifts to:



> \*\*threat modeling, ASVS-based verification, dependency/code review,

> CSP/Trusted Types enforcement, server-side authorization tests,

> refresh-family race/replay tests, and testing that `Lock` genuinely makes

> every sensitive endpoint unusable.\*\*



These are not optional "cleanup" activities.



They verify that the architecture actually provides the properties claimed by

the design.



\---



\# 32. Threat Modeling



Create an explicit threat model before considering the security architecture

complete.



At minimum model:



\## Assets



\- trading authority

\- private keys

\- BFF sessions

\- OAuth credentials

\- account data

\- transaction authorization

\- recovery credentials

\- MFA state



\## Trust Boundaries



Browser

&#x20;   ↕



BFF

&#x20;   ↕



OAuth Authorization Server

&#x20;   ↕



Trading APIs

&#x20;   ↕



databases / session storage / key infrastructure



\## Threat Actors



\- remote unauthenticated attacker

\- authenticated malicious user

\- XSS attacker

\- CSRF attacker

\- stolen-session attacker

\- compromised dependency

\- compromised browser extension

\- compromised build pipeline

\- malicious/replayed API client

\- attacker possessing an old refresh token



\## Critical Questions



Can an attacker trade with only the BFF session?



Can an attacker trade after Lock?



Can an old vault signature be replayed?



Can an order signature authorize modified parameters?



Can an old refresh token resurrect a revoked session?



Can two simultaneous refreshes bypass rotation detection?



Can two simultaneous execution requests consume one authorization?



Can XSS obtain/export the private key?



Can XSS invoke signing without meaningful restrictions?



Can CSRF cause a sensitive operation?



Can a compromised dependency bypass transaction confirmation?



Can logout fail to invalidate server authority?



Can a network error accidentally become authorization success?



Each answer should correspond to an enforceable security control and an

automated test where practical.



\---



\# 33. ASVS-Based Verification



Use OWASP Application Security Verification Standard (ASVS) as a verification

framework rather than relying solely on developer intuition.



Map applicable ASVS requirements to:



IMPLEMENTED

TESTED

NOT APPLICABLE

REQUIRES REVIEW



Particular attention should be given to:



\- authentication

\- session management

\- access control

\- input validation

\- cryptography

\- stored data

\- communication security

\- malicious code/dependencies

\- business logic

\- API security

\- configuration

\- logging



For this application, aim beyond merely satisfying baseline web-app controls

because cryptographic and trading authority create unusually high-impact

failure modes.



\---



\# 34. Authorization Test Matrix



Create automated negative authorization tests.



Do not test only:



"Does the valid request work?"



Also test:



"Can every invalid security state fail?"



For each sensitive endpoint test:



logged out

authenticated + locked

authenticated + unlocked

wrong account

wrong user

wrong scope

expired step-up

missing signature

invalid signature

modified parameters

wrong audience

wrong transaction ID

expired nonce

replayed nonce

already-consumed transaction

revoked session

concurrent execution



Example invariant:



Authenticated + Locked

&#x20;       │

&#x20;       ├── GET /portfolio            → allowed

&#x20;       │

&#x20;       ├── GET /market-data          → allowed

&#x20;       │

&#x20;       ├── POST /execute-order       → DENIED

&#x20;       │

&#x20;       ├── POST /withdraw            → DENIED

&#x20;       │

&#x20;       └── POST /export-secret       → DENIED



This test suite establishes whether Lock has actual security meaning.



\---



\# 35. Explicit Lock Invariant Testing



Make this a dedicated security test suite.



The invariant should be:



> After `Lock` completes, no operation classified as requiring cryptographic

> authority can succeed until a new successful unlock establishes new

> cryptographic authority.



Test Lock during:



\- idle state

\- prepared transaction

\- transaction confirmation

\- concurrent requests

\- multiple tabs

\- network interruption

\- page navigation

\- background/foreground transition

\- API retry

\- transaction timeout



Also test stale references.



If component A obtained signing authority before Lock, that reference must not

remain usable afterward.



Lock should invalidate the authority itself, not merely remove the newest

reference to it.



\---



\# 36. Refresh-Family Race and Replay Testing



Even though OAuth refresh now lives inside the BFF, explicitly test:



normal rotation



simultaneous refresh



old-generation replay



latest-generation theft



revoked-family refresh



expired-family refresh



logout followed by refresh attempt



logout-all-devices followed by refresh attempt



server restart during rotation



database transaction failure during rotation



concurrent BFF workers attempting refresh



The security property must survive concurrency and partial failure.



\---



\# 37. CSP and Trusted Types Verification



Do not merely configure CSP.



Test it.



Attempt representative DOM-XSS payloads against:



\- query parameters

\- URL fragments

\- API-returned strings

\- user-generated content

\- error messages

\- markdown rendering

\- HTML rendering

\- dynamic script creation

\- dynamic navigation

\- third-party components



Run CSP in reporting mode during controlled deployment/testing and review

violations.



Then enforce.



Trusted Types policies should receive dedicated code review.



\---



\# 38. Dependency and Code Review



Security-critical code should receive explicit review boundaries.



Highest-priority code includes:



vault unlock

KDF handling

CryptoKey creation/import

signing authorization

canonical serialization

transaction challenge generation

signature verification

nonce consumption

authorization middleware

session creation/revocation

OAuth refresh rotation

CSRF enforcement

step-up authorization

logout

Lock



These components should be kept relatively small and understandable.



Complexity in security-critical code should be treated as a security cost.



\---



\# 39. Property-Based and Adversarial Testing



Where practical, test security properties rather than only expected examples.



Examples:



For arbitrary modification M of a signed transaction T:



&#x20;   verify(signature(T), M(T)) == false



For consumed challenge C:



&#x20;   execute(C) succeeds at most once



For locked state L:



&#x20;   every sensitive endpoint == denied



For revoked session S:



&#x20;   every authenticated operation == denied



For expired authorization A:



&#x20;   execute(A) == denied



Fuzz:



\- canonical transaction serialization

\- signature parsing

\- authorization inputs

\- malformed JWTs where applicable

\- challenge parsing

\- API boundary validation



\---



\# 40. Final Security Priorities



Once the architecture is implemented, prioritize work approximately as:



1\. Correct server-side authorization

2\. Vault key/signing isolation

3\. Operation-bound signatures and replay prevention

4\. Correct Lock semantics

5\. BFF session security

6\. OAuth refresh rotation/revocation correctness

7\. XSS prevention: CSP + Trusted Types + safe coding

8\. CSRF protection

9\. Dependency/build-chain security

10\. Step-up authentication

11\. Logging/detection

12\. Continuous security verification



Do not endlessly add authentication layers while these controls remain

untested.



\---



\# 41. Final Security Invariants



The system should be considered correct only if all of the following remain

true:



\## Identity



A valid browser session establishes identity only.



\## OAuth



OAuth tokens never enter normal browser JavaScript.



\## Authorization



Every protected resource performs trusted server-side authorization.



\## Vault



The encrypted vault remains unusable without successful unlock.



\## Lock



Lock removes all cryptographic authority while preserving authenticated

identity.



\## Sensitive Operations



A BFF session alone cannot authorize an operation classified as requiring

vault authority.



\## Transaction Integrity



Cryptographic authorization applies only to the exact operation and exact

parameters the user authorized.



\## Replay



A previously consumed sensitive authorization cannot be used again.



\## Step-Up



Exceptionally sensitive account/security operations require recent additional

authorization.



\## Logout



Logout revokes server-side session continuity rather than merely clearing UI

state.



\## Expiration



Authentication and cryptographic authority cannot be extended indefinitely

through background refresh.



\## Failure



Security-control failures result in denial rather than silent downgrade.



\## Verification



These properties are continuously demonstrated through automated negative,

race, replay, authorization, and Lock-state tests.



\---



\# 42. Security Standard / Research Basis



The architecture should be reviewed against current primary or recognized

security guidance, particularly:



\- IETF OAuth 2.0 Security Best Current Practice — RFC 9700

\- IETF OAuth 2.0 for Browser-Based Applications

\- IETF Demonstrating Proof of Possession (DPoP) — RFC 9449

\- IETF JSON Web Token Best Current Practices — RFC 8725 and its current

&#x20; successor work

\- W3C Web Cryptography API

\- W3C Trusted Types

\- W3C Content Security Policy

\- OWASP Application Security Verification Standard (ASVS)

\- OWASP Session Management Cheat Sheet

\- OWASP Authentication Cheat Sheet

\- OWASP Authorization Cheat Sheet

\- OWASP Cross-Site Scripting Prevention Cheat Sheet

\- OWASP Content Security Policy Cheat Sheet

\- OWASP CSRF Prevention Cheat Sheet



The important objective is not accumulating controls.



It is establishing a small number of strong security boundaries and then

proving those boundaries remain intact under malicious input, concurrency,

replay, XSS, CSRF, stale state, partial failure, and compromised-session

conditions.



\---



\# Final Architecture Decision



Use:



Browser

&#x20;   │

&#x20;   │ opaque HttpOnly session

&#x20;   ▼

BFF

&#x20;   │

&#x20;   │ owns OAuth tokens

&#x20;   │ owns refresh rotation

&#x20;   │ performs authorization

&#x20;   ▼

Trading APIs



while independently maintaining:



Encrypted Client Vault

&#x20;   │

&#x20;   │ master-password unlock

&#x20;   ▼

Non-Extractable Cryptographic Authority

&#x20;   │

&#x20;   │ exact-operation authorization

&#x20;   ▼

BFF Verification

&#x20;   │

&#x20;   ▼

Sensitive Operation



This provides the key separation:



\*\*Authentication proves identity.\*\*



\*\*The BFF controls API authority.\*\*



\*\*Unlock provides cryptographic authority.\*\*



\*\*Step-up establishes exceptional user authorization.\*\*



\*\*Lock removes cryptographic authority without destroying identity.\*\*



\*\*Logout destroys session continuity.\*\*



And once those boundaries are implemented, the highest-return work shifts

from adding more authentication mechanisms to proving that those boundaries

actually hold through threat modeling, ASVS verification, security-focused

code review, dependency review, CSP/Trusted Types enforcement, adversarial

authorization testing, refresh-family race/replay testing, and explicit

verification that `Lock` makes every sensitive operation impossible.

