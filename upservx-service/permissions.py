"""
Group-based access control for UpservX.

Linux group → subsystem mapping
───────────────────────────────────────────────────────────────────────────────
  sudo / wheel   →  full administrator access (all endpoints)
  docker         →  container management (Docker), Docker images, App Store
  lxd  / lxc     →  container management (LXC),  LXC images
  libvirt / kvm  →  virtual machine management, ISO management

Any group not listed above gives access only to read-only metadata endpoints
(/metrics, /, auth endpoints).
"""

import grp
import pwd
from typing import Set

# ── Group sets ────────────────────────────────────────────────────────────────

ADMIN_GROUPS: Set[str] = {"sudo", "wheel"}
DOCKER_GROUPS: Set[str] = {"docker"}
LXD_GROUPS: Set[str] = {"lxd", "lxc"}
CONTAINER_GROUPS: Set[str] = DOCKER_GROUPS | LXD_GROUPS
LIBVIRT_GROUPS: Set[str] = {"libvirt", "kvm"}

# Non-PAM principals (API key, cluster tokens) receive implicit admin rights.
SYSTEM_PRINCIPALS: Set[str] = {"api-key", "cluster-node", "cluster-master"}

# ── URL-prefix lists ──────────────────────────────────────────────────────────

# Paths that require docker / lxd group (or admin)
_CONTAINER_PREFIXES = ("/containers", "/images")

# Paths that require libvirt / kvm group (or admin)
_VM_PREFIXES = ("/vms", "/isos")

# Paths that require full admin (sudo / wheel)
_ADMIN_PREFIXES = (
    "/firewall",
    "/network",
    "/drives",
    "/users",
    "/groups",
    "/services",
    "/logs",
    "/activity-log",
    "/settings",
    "/backup",
    "/proxy",
    "/system/shell",
)


# ── Group resolution ──────────────────────────────────────────────────────────

def get_user_groups(username: str) -> Set[str]:
    """Return all Linux group names the *username* belongs to.

    Returns an empty set for non-PAM principals; the caller must handle those
    via :func:`is_admin` which treats them as full admin.
    """
    if username in SYSTEM_PRINCIPALS:
        return set()
    try:
        pw = pwd.getpwnam(username)
        groups: Set[str] = set()
        for g in grp.getgrall():
            if username in g.gr_mem or g.gr_gid == pw.pw_gid:
                groups.add(g.gr_name)
        return groups
    except KeyError:
        return set()


# ── Permission predicates ─────────────────────────────────────────────────────

def is_admin(username: str, groups: Set[str]) -> bool:
    """True if the user has full administrator (sudo/wheel) access."""
    return username in SYSTEM_PRINCIPALS or bool(groups & ADMIN_GROUPS)


def has_container_access(username: str, groups: Set[str]) -> bool:
    """True if the user may manage containers (docker or lxd group, or admin)."""
    return is_admin(username, groups) or bool(groups & CONTAINER_GROUPS)


def has_vm_access(username: str, groups: Set[str]) -> bool:
    """True if the user may manage VMs and ISOs (libvirt/kvm group, or admin)."""
    return is_admin(username, groups) or bool(groups & LIBVIRT_GROUPS)


def check_path_permission(username: str, groups: Set[str], path: str) -> bool:
    """Return True when *username* (with resolved *groups*) may access *path*.

    This is the single source of truth called by the auth middleware.
    """
    # Containers & images: docker / lxd group (or admin)
    for prefix in _CONTAINER_PREFIXES:
        if path.startswith(prefix):
            return has_container_access(username, groups)

    # VMs & ISOs: libvirt / kvm group (or admin)
    for prefix in _VM_PREFIXES:
        if path.startswith(prefix):
            return has_vm_access(username, groups)

    # Admin-only subsystems
    for prefix in _ADMIN_PREFIXES:
        if path.startswith(prefix):
            return is_admin(username, groups)

    # Everything else (/metrics, /, /auth/*, /cluster/*) — allow any authenticated user
    return True


def get_permission_summary(username: str, groups: Set[str]) -> dict:
    """Return a JSON-serialisable summary of the user's permissions."""
    return {
        "username": username,
        "groups": sorted(groups),
        "permissions": {
            "admin": is_admin(username, groups),
            "containers": has_container_access(username, groups),
            "vms": has_vm_access(username, groups),
        },
    }
