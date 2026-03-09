# Authentication & Middleware

**File:** `upservx-service/main.py`

---

## Overview

UpservX uses three authentication mechanisms:

| Mechanism | Header Format | Description |
|---|---|---|
| **PAM Basic Auth** | `Authorization: Basic base64(user:pass)` | Linux PAM against local user accounts |
| **API Key** | `Authorization: Bearer <api-key>` | Static API key from `settings.json` |
| **Cluster Token** | `Authorization: Bearer <cluster-key>` | Token for cluster node communication |
| **Cookie Fallback** | Cookie `auth` | Contains the base64 token or full header value |

---

## PAM Authentication

The middleware uses `python-pam` via `pam.pam().authenticate(username, password)`.

This means:
- Any Linux user on the host system with a valid password can log in.
- Access rights are determined **not** by the password, but by the user's **Linux groups** (see [Permissions](./permissions.md)).

```python
pam_auth = pam.pam()
if not pam_auth.authenticate(username, password):
    return Response(status_code=401)
request.state.user = username
```

---

## API Key Authentication

An API key can be generated in the settings. Bearer token requests are validated against this key.

```python
settings = load_settings()
if settings.api_key and token == settings.api_key:
    request.state.user = "api-key"
```

The principal `"api-key"` is treated as a **system principal** with full admin access (no group check required).

---

## Cluster Token Authentication

Cluster nodes communicate using a shared `cluster_key`:

```python
cluster_key = get_cluster_key()
if cluster_key and token == cluster_key:
    request.state.user = "cluster-node"  # Admin rights
```

Master nodes use a separate `master_config["key"]`:

```python
master_config = read_master_config()
if master_config and master_config.get("key") == token:
    request.state.user = "cluster-master"  # Admin rights
```

Both are treated as **system principals** with full access.

---

## Auth Middleware Flow

```
HTTP Request
    │
    ├── OPTIONS (CORS preflight) → pass through directly
    ├── WebSocket upgrade → pass through (WS handler authenticates itself)
    ├── /app-store/apps/*/icon (GET) → public, no auth
    ├── /isos/*/file (GET) → public, no auth
    ├── /settings/customization (GET) → public (login screen)
    ├── /auth/login (POST) → public
    ├── /cluster/register (POST) → authenticated internally
    ├── /cluster/export|download|upload|import → authenticated internally
    │
    └── All other endpoints:
          │
          ├── Authorization header present?
          │     No → check Cookie "auth"
          │          No cookie → 401
          │
          ├── "Basic ..." → PAM → 401 on failure
          ├── "Bearer ..." → API key or cluster key → 401 on failure
          └── Other scheme → 401
```

---

## Rate Limiting

In-memory rate limiter (no Redis, per-process):

| Endpoint | Limit |
|---|---|
| `/auth/login` | 10 attempts / 60 seconds per IP |
| WebSocket ticket creation | 20 tickets / 60 seconds per IP |

Implemented via `_check_rate_limit(key, max_attempts, window_seconds)`.

**Note:** These rate limits are purely in-memory. They reset on process restart. For production environments, an external rate limiter (e.g. Nginx `limit_req`) should be added upstream.

---

## WebSocket Tickets

To open WebSocket connections (terminal, VNC), a one-time ticket is used:

```
POST /system/ws-ticket   → returns a short-lived ticket
WebSocket connect with ?ticket=<ticket>   → ticket is consumed
```

The ticket system prevents WS connections from being opened without prior HTTP authentication. Implemented in `ws_tickets.py`.
