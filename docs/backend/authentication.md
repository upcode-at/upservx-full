# Authentication and sessions

**Primary files:** `upservx-service/main.py`, `api/auth.py`,
`lib/session_tokens.py`, `lib/api_tokens.py`, and `lib/totp.py`

## Authentication mechanisms

| Mechanism | Transport | Purpose |
|---|---|---|
| User session | HTTPS-only `auth` cookie or `Authorization: Bearer <session>` | Browser and user API sessions created after PAM login |
| API token | `Authorization: Bearer upx_...` | Automation with an explicit role and scopes |
| Cluster signature | HMAC signature headers over the complete request | Internal node-to-node routes on the dedicated TLS listener |

Passwords are accepted only by `POST /auth/login` and verified with Linux PAM.
All password checks explicitly use the `/etc/pam.d/upservx` service, which the
installer configures to include Debian's `common-auth` and `common-account`
policies. PAM failures are logged server-side with their code and reason, while
the API returns only a generic credential error. Passwords are never placed in
cookies, session files, or diagnostic logs. If 2FA is enabled, the
short-lived first-factor record contains only the username, timestamps, an
attempt counter, and a hash of the random login token.

## User sessions

Successful login creates a signed session containing the username, issue and
expiry timestamps, and a random session ID. `/etc/upservx/sessions.json` stores
only the SHA-256 hash of that session ID. A valid signature is therefore not
enough: the server-side record must still exist and be unexpired.

Logout revokes the current record immediately. Password changes revoke every
session for the user; disabling 2FA revokes the user's other sessions. Legacy
stateless session tokens are rejected and require a new login.

The cookie defaults are:

- `Secure`, `HttpOnly`, `SameSite=Strict`, and `Path=/`
- one-hour `Max-Age` and an explicit expiry timestamp
- no `Domain` attribute unless one is configured
- deletion with the same path, domain, secure, and SameSite attributes

The response body does not expose the session token. Configure deployments
with HTTPS before login; `UPSERVX_COOKIE_SECURE=false` is intended only for an
explicit local development environment.

| Environment variable | Default | Constraint |
|---|---|---|
| `UPSERVX_SESSION_TTL_SECONDS` | `3600` | 300 to 86400 seconds |
| `UPSERVX_COOKIE_SECURE` | `true` | Must remain true with `SameSite=None` |
| `UPSERVX_COOKIE_SAMESITE` | `strict` | `strict`, `lax`, or `none` |
| `UPSERVX_COOKIE_DOMAIN` | unset | Optional explicit cookie domain |
| `UPSERVX_SESSION_SECRET` | generated on disk | At least 32 bytes when supplied |

## API tokens

API tokens replace the former single plaintext key in `settings.json`. Token
records in `/etc/upservx/api_tokens.json` contain only SHA-256 hashes plus
names, roles, scopes, expiry, and revocation metadata. Plaintext is returned
once when a token is created.

Roles are `admin`, `operator`, and `read-only`. A request must be allowed by
both its role and its exact action scope, such as `containers:read`,
`containers:*`, or `*`. Unknown routes are denied. Even an administrator token
cannot call internal cluster routes; those require a verified cluster
signature.

| Method | Path | Description |
|---|---|---|
| `GET` | `/settings/api-tokens` | List safe token metadata |
| `POST` | `/settings/api-tokens` | Create a role- and scope-bound token |
| `DELETE` | `/settings/api-tokens/{token_id}` | Revoke a token immediately |
| `POST` | `/settings/api-key` | Compatibility alias that creates a revocable admin token |

At startup, a legacy `settings.json` `api_key` is hashed into a revocable token
record and removed from the settings file.

## Cluster authentication

Internal cluster and HA requests use HMAC-SHA256 signatures with node identity,
key ID, timestamp, nonce, method, exact target, and body digest. Replay nonces
are persisted under a cross-process file lock. These requests are accepted only
on the dedicated HTTPS listener, and peers pin the authenticated node CA.

## WebSockets

Browser WebSockets use short-lived, one-time tickets obtained from
`GET /auth/ws-ticket`. API tokens may be supplied in an `Authorization` header
by non-browser clients, but are not accepted in query strings where access
tokens could leak into URLs and logs.

## Rate limiting

Login is limited to 10 attempts per IP per minute and WebSocket-ticket creation
to 20 requests per IP per minute. The browser-facing API is deliberately run as
one Uvicorn process, so these buckets and one-time WebSocket tickets are
consistent. The separate TLS process accepts signed cluster requests only.
