# Permission system

**File:** `upcode-harbor-service/lib/permissions.py`

## Deny-by-default route policy

Every HTTP method and FastAPI route template is registered in
`ROUTE_POLICIES` with an explicit action. A path with the wrong method, a newly
added route without a policy, and an unknown path are denied before any
administrator check. CI compares every registered FastAPI route with this
table.

Read and mutation actions are separate, including:

- `containers:read` and `containers:write`
- `vms:read`, `vms:write`, and dedicated VM-network actions
- `storage:read` and `storage:write`
- `admin:read` and `admin:write`
- `cluster:read`, `cluster:write`, and internal cluster actions

## Linux user roles

PAM authenticates the user; current Linux group membership determines access.

| Linux group | Access |
|---|---|
| `sudo`, `wheel`, or UID 0 | All known user-facing routes |
| `docker`, `lxd`, `lxc` | Container inventory, read, and mutation routes |
| `libvirt`, `kvm` | VM, ISO, and VM-network routes |
| `disk`, `storage` | Physical-storage routes |
| `adm`, `log` | Log reads |
| `tty` | Interactive system shell capability |

Administrator status does not grant access to internal cluster transport
routes. Those require a verified signed cluster principal.

## API-token roles and scopes

API tokens do not inherit Linux groups. Authorization first checks the token
role and then its scopes:

| Role | Maximum access before scopes are applied |
|---|---|
| `admin` | Every known user-facing action |
| `operator` | Container, VM, storage, log, and general system actions |
| `read-only` | Safe reads, including explicitly scoped admin and cluster reads |

Scopes can match one action (`containers:read`), one subsystem
(`containers:*`), or all user-facing actions (`*`). Both the role and a scope
must allow the request. No API-token role can access `cluster-internal:*`.

## Cluster principals

`cluster-node` and `cluster-master` are not administrators. After HMAC, peer,
TLS-listener, time-window, and replay validation, they may call only explicitly
classified internal cluster routes plus the limited container and VM inventory
routes required for resource discovery.

## Public and self-service routes

Public access is limited to exact method/path pairs such as login and public
branding assets. Session self-service routes cover logout, current-user
metadata, 2FA, password changes, and WebSocket tickets. Prefixes are never used
as an implicit authorization fallback.

## Permission summary

`GET /auth/me` returns the current Linux username, groups, and a UI-oriented
summary:

```json
{
  "username": "alice",
  "groups": ["docker", "adm"],
  "permissions": {
    "admin": false,
    "containers": true,
    "vms": false,
    "storage": false,
    "shell": false,
    "logs": true
  }
}
```

This summary controls navigation visibility; backend route authorization
remains the security boundary.
