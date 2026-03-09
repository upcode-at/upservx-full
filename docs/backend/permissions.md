# Permission System

**File:** `upservx-service/permissions.py`

---

## Concept

UpservX uses a **group-based access control system** built directly on top of **Linux system groups**. There is no separate user/role model in a database — instead, the Linux group memberships of the user (as defined in `/etc/group`) are read at runtime.

**Principle:** Which Linux groups a user belongs to determines which API endpoints they can access.

---

## Group Mapping

| Linux Group(s) | Access To |
|---|---|
| `sudo`, `wheel` | **Full access (admin)** to all endpoints |
| `docker` | Container management (Docker), Docker images, app store |
| `lxd`, `lxc` | Container management (LXC), LXC images |
| `libvirt`, `kvm` | Virtual machines, ISO management |
| `disk`, `storage` | Physical storage management (drives, ZFS) |
| `tty` | System shell access (terminal) |
| `adm`, `log` | Read-only log access |
| None of the above | Read-only metadata only (`/metrics`, `/`, auth endpoints) |

---

## System Principals (Special Case)

Non-PAM principals receive **implicit admin access** and bypass the group check:

| Principal | Description |
|---|---|
| `api-key` | Requests via API key authentication |
| `cluster-node` | Cluster child node |
| `cluster-master` | Cluster master node |

---

## URL Prefix → Permission Mapping

| URL Prefix | Required Permission |
|---|---|
| `/containers` | `docker` or `lxd`/`lxc` group (or admin) |
| `/images` | `docker` or `lxd`/`lxc` group (or admin) |
| `/vms` | `libvirt` or `kvm` group (or admin) |
| `/isos` | `libvirt` or `kvm` group (or admin) |
| `/drives` | `disk` or `storage` group (or admin) |
| `/system/shell` | `tty` or admin |
| `/logs` | `adm` or `log` group (or admin) |
| `/activity-log` | `adm` or `log` group (or admin) |
| `/firewall` | **Admin** (`sudo`/`wheel`) |
| `/network` | **Admin** |
| `/users` | **Admin** |
| `/groups` | **Admin** |
| `/services` | **Admin** |
| `/settings` | **Admin** |
| `/backup` | **Admin** |
| `/proxy` | **Admin** |

---

## Implementation

### Reading Groups

```python
def get_user_groups(username: str) -> Set[str]:
    """Reads all Linux groups of the user from /etc/group."""
    pw = pwd.getpwnam(username)
    groups = set()
    for g in grp.getgrall():
        if username in g.gr_mem or g.gr_gid == pw.pw_gid:
            groups.add(g.gr_name)
    return groups
```

### Permission Check

```python
def check_path_permission(username: str, groups: Set[str], path: str) -> bool:
    """Single source of truth for access checks."""
    # Checks URL prefix against group sets
    # Returns: True = access allowed, False = 403
```

### Helper Functions

| Function | Description |
|---|---|
| `is_admin(username, groups)` | True if `sudo`/`wheel` or system principal |
| `has_container_access(username, groups)` | Docker/LXC group or admin |
| `has_vm_access(username, groups)` | libvirt/kvm group or admin |
| `has_storage_access(username, groups)` | disk/storage group or admin |
| `has_shell_access(username, groups)` | tty group or admin |
| `has_log_access(username, groups)` | adm/log group or admin |
| `get_permission_summary(username)` | Dict with all permissions (for frontend) |

---

## Permission Summary API

The frontend calls `GET /auth/permissions` and receives:

```json
{
  "is_admin": true,
  "has_container_access": true,
  "has_vm_access": true,
  "has_storage_access": true,
  "has_shell_access": true,
  "has_log_access": true,
  "groups": ["sudo", "docker", "libvirt", "tty"]
}
```

This information controls the visibility of UI elements in the frontend.

---

## Typical User Configurations

### Container Management Only
```bash
useradd -m -G docker containeradmin
```

### VM Management Only
```bash
useradd -m -G libvirt,kvm vmadmin
```

### Full Admin
```bash
useradd -m -G sudo sysadmin
```

### Monitoring Only (read logs)
```bash
useradd -m -G adm monitor
```
