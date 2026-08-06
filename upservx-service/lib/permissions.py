"""Method- and route-based authorization for UpservX.

Every HTTP endpoint must be present in ROUTE_POLICIES. Requests that do not
match a registered method/path pair are denied, including requests made by
administrators and system principals. This makes newly added routes fail closed
until their required action is chosen explicitly.

Linux groups map to subsystem actions:

* sudo / wheel / root: all actions on known routes
* docker / lxd / lxc: container and image read/write actions
* libvirt / kvm: VM, ISO, and VM-network read/write actions
* disk / storage: physical-storage read/write actions
* adm / log: log read actions
* tty: shell access (no shell HTTP route is currently registered)

API tokens are authorized separately by their explicit role and scopes.
Cluster principals are deliberately not administrators and can use only the
explicit inter-node routes plus the two inventory routes needed by cluster
resource discovery.
"""

from __future__ import annotations

import grp
import pwd
import re
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Pattern, Set


# Group and principal sets ----------------------------------------------------

ADMIN_GROUPS: Set[str] = {"sudo", "wheel", "root"}
DOCKER_GROUPS: Set[str] = {"docker"}
LXD_GROUPS: Set[str] = {"lxd", "lxc"}
CONTAINER_GROUPS: Set[str] = DOCKER_GROUPS | LXD_GROUPS
LIBVIRT_GROUPS: Set[str] = {"libvirt", "kvm"}
STORAGE_GROUPS: Set[str] = {"disk", "storage"}
SHELL_GROUPS: Set[str] = {"tty"}
LOG_GROUPS: Set[str] = {"adm", "log"}

API_PRINCIPALS: Set[str] = set()
CLUSTER_PRINCIPALS: Set[str] = {"cluster-node", "cluster-master"}
SYSTEM_PRINCIPALS: Set[str] = API_PRINCIPALS | CLUSTER_PRINCIPALS


class PermissionAction(str, Enum):
    """Actions assigned to explicit method/path pairs."""

    PUBLIC = "public"
    AUTH_SELF = "auth:self"
    SYSTEM_READ = "system:read"
    CONTAINER_INVENTORY = "containers:inventory"
    CONTAINER_READ = "containers:read"
    CONTAINER_WRITE = "containers:write"
    VM_INVENTORY = "vms:inventory"
    VM_READ = "vms:read"
    VM_WRITE = "vms:write"
    VM_NETWORK_READ = "vm-networks:read"
    VM_NETWORK_WRITE = "vm-networks:write"
    STORAGE_READ = "storage:read"
    STORAGE_WRITE = "storage:write"
    LOG_READ = "logs:read"
    ADMIN_READ = "admin:read"
    ADMIN_WRITE = "admin:write"
    HOST_CONFIG_READ = "host-config:read"
    HOST_CONFIG_WRITE = "host-config:write"
    CLUSTER_READ = "cluster:read"
    CLUSTER_WRITE = "cluster:write"
    CLUSTER_INFO_READ = "cluster:info"
    CLUSTER_INTERNAL_READ = "cluster-internal:read"
    CLUSTER_INTERNAL_WRITE = "cluster-internal:write"


def _build_route_policies() -> Mapping[tuple[str, str], PermissionAction]:
    """Build the immutable route policy table and reject duplicate entries."""

    policies: dict[tuple[str, str], PermissionAction] = {}

    def add(action: PermissionAction, method: str, *paths: str) -> None:
        for path in paths:
            key = (method.upper(), path)
            if key in policies:
                raise RuntimeError(f"Duplicate authorization policy for {method} {path}")
            policies[key] = action

    # Public routes. These are the only HTTP requests that bypass authentication.
    add(
        PermissionAction.PUBLIC,
        "POST",
        "/auth/login",
        "/auth/2fa/complete",
    )
    add(
        PermissionAction.PUBLIC,
        "GET",
        "/health/live",
        "/health/ready",
        "/containers/app-store/apps/{app_id}/icon",
        "/isos/{name}/file",
        "/settings/customization",
        "/settings/customization/logo/file",
        "/settings/customization/banner/file",
    )

    # Authenticated metadata and self-service authentication routes.
    add(
        PermissionAction.SYSTEM_READ,
        "GET",
        "/",
        "/metrics",
        "/info",
        "/openapi.json",
        "/docs",
        "/docs/oauth2-redirect",
        "/redoc",
    )
    add(
        PermissionAction.AUTH_SELF,
        "GET",
        "/auth/ws-ticket",
        "/auth/me",
        "/auth/2fa/status",
    )
    add(
        PermissionAction.AUTH_SELF,
        "POST",
        "/auth/logout",
        "/auth/2fa/setup",
        "/auth/2fa/verify-setup",
        "/auth/2fa/disable",
        "/auth/change-password",
    )

    # Container, image, Compose, App Store, volume, and Docker storage routes.
    add(PermissionAction.CONTAINER_INVENTORY, "GET", "/containers")
    add(
        PermissionAction.CONTAINER_READ,
        "GET",
        "/containers/{name}/logs",
        "/containers/{name}",
        "/containers/compose/stacks",
        "/containers/compose-projects",
        "/containers/compose-projects/{project_name}/services/{service_name}",
        "/containers/compose-projects/{project_name}/compose",
        "/containers/app-store/apps",
        "/containers/app-store/categories",
        "/containers/app-store/apps/{app_id}",
        "/containers/volumes",
        "/containers/storages",
        "/images",
    )
    add(
        PermissionAction.CONTAINER_WRITE,
        "POST",
        "/containers",
        "/containers/{name}/start",
        "/containers/{name}/stop",
        "/containers/{name}/restart",
        "/containers/build",
        "/containers/build/stream",
        "/containers/compose",
        "/containers/compose/{project_name}/start",
        "/containers/compose/{project_name}/stop",
        "/containers/compose-projects",
        "/containers/compose-projects/{project_name}/services",
        "/containers/compose-projects/{project_name}/start",
        "/containers/compose-projects/{project_name}/stop",
        "/containers/app-store/apps/{app_id}/install",
        "/containers/app-store/apps/{project_name}/update",
        "/containers/storages",
        "/containers/volumes",
        "/images/pull",
    )
    add(
        PermissionAction.CONTAINER_WRITE,
        "PUT",
        "/containers/compose-projects/{project_name}/services/{service_name}",
        "/containers/compose-projects/{project_name}/compose",
    )
    add(
        PermissionAction.CONTAINER_WRITE,
        "DELETE",
        "/containers/{name}",
        "/containers/compose/{project_name}",
        "/containers/compose-projects/{project_name}/services/{service_name}",
        "/containers/compose-projects/{project_name}",
        "/containers/app-store/apps/{project_name}/uninstall",
        "/containers/volumes/{name}",
        "/containers/storages/{name}",
        "/images/{image}",
    )

    # VM and ISO routes.
    add(PermissionAction.VM_INVENTORY, "GET", "/vms")
    add(
        PermissionAction.VM_READ,
        "GET",
        "/vms/{name}/vnc",
        "/vms/{name}/snapshots",
        "/vms/exports/jobs/{job_id}",
        "/vms/exports/{filename}",
        "/isos",
    )
    add(
        PermissionAction.VM_WRITE,
        "POST",
        "/vms",
        "/vms/{name}/start",
        "/vms/{name}/shutdown",
        "/vms/{name}/clone",
        "/vms/{name}/snapshots",
        "/vms/{name}/snapshots/{snapshot_name}/restore",
        "/vms/{name}/export",
        "/vms/import",
        "/isos/download",
        "/isos",
    )
    add(PermissionAction.VM_WRITE, "PATCH", "/vms/{name}")
    add(
        PermissionAction.VM_WRITE,
        "DELETE",
        "/vms/{name}",
        "/vms/{name}/snapshots/{snapshot_name}",
        "/isos/{name}",
    )

    # VM network routes intentionally use their own read/write actions.
    add(PermissionAction.VM_NETWORK_READ, "GET", "/vm-networks")
    add(PermissionAction.VM_NETWORK_WRITE, "POST", "/vm-networks")
    add(
        PermissionAction.VM_NETWORK_WRITE,
        "POST",
        "/vm-networks/{name}/start",
        "/vm-networks/{name}/stop",
    )
    add(PermissionAction.VM_NETWORK_WRITE, "DELETE", "/vm-networks/{name}")

    # Physical storage routes.
    add(PermissionAction.STORAGE_READ, "GET", "/drives", "/drives/zfs")
    add(
        PermissionAction.STORAGE_WRITE,
        "POST",
        "/drives/mount",
        "/drives/unmount",
        "/drives/format",
        "/drives/zfs",
    )

    # Log routes.
    add(
        PermissionAction.LOG_READ,
        "GET",
        "/logs",
        "/logs/activity",
        "/activity-log",
        "/logs/{name:path}",
    )

    # Admin-only read routes outside the cluster subsystem.
    add(
        PermissionAction.ADMIN_READ,
        "GET",
        "/firewall/rules",
        "/firewall/statistics",
        "/network/interfaces",
        "/network/settings",
        "/users",
        "/users/{username}/keys",
        "/groups",
        "/services",
        "/settings",
        "/settings/vpn/file",
        "/settings/vpn/status",
        "/settings/notifications",
        "/settings/api-tokens",
        "/backup/servers",
        "/backup/servers/{server_id}",
        "/backup/servers/{server_id}/info",
        "/backup/jobs",
        "/backup/jobs/{job_id}",
        "/backup/jobs/{job_id}/progress",
        "/backup/instances",
        "/backup/instances/{instance_id}",
        "/backup/cron-jobs",
        "/ssh-keys",
        "/ssh-keys/{key_name}",
        "/proxy/status",
        "/proxy/configs",
        "/proxy/certificates",
        "/security/fail2ban",
        "/security/packages",
        "/security/certificates",
        "/security/ports",
        "/security/cve",
        "/security/container-cve",
        "/jobs",
        "/jobs/{job_id}",
    )

    # Admin-only mutation routes outside the cluster subsystem.
    add(
        PermissionAction.ADMIN_WRITE,
        "POST",
        "/firewall/rules",
        "/firewall/chains/{chain}/flush",
        "/firewall/port-forward",
        "/firewall/masquerade",
        "/firewall/save",
        "/firewall/load",
        "/network/settings",
        "/network/interfaces/{name}",
        "/users",
        "/groups",
        "/services/{name}/start",
        "/services/{name}/stop",
        "/services/{name}/enable",
        "/services/{name}/disable",
        "/settings",
        "/settings/api-key",
        "/settings/api-tokens",
        "/settings/vpn/upload",
        "/settings/vpn/start",
        "/settings/vpn/stop",
        "/settings/notifications",
        "/settings/notifications/test/email",
        "/settings/notifications/test/webhook",
        "/settings/update",
        "/settings/customization",
        "/settings/customization/logo",
        "/settings/customization/banner",
        "/backup/servers",
        "/backup/servers/{server_id}/test",
        "/backup/jobs",
        "/backup/jobs/{job_id}/execute",
        "/backup/jobs/{job_id}/trigger",
        "/backup/instances/{instance_id}/restore",
        "/backup/instances/{instance_id}/verify",
        "/ssh-keys/generate",
        "/ssh-keys/import",
        "/ssh-keys/{key_name}/test",
        "/proxy/configs",
        "/proxy/certificates/obtain",
        "/proxy/certificates/renew",
        "/security/fail2ban/unban",
        "/security/packages/upgrade",
        "/security/packages/upgrade/{name}",
        "/jobs/{job_id}/cancel",
        "/jobs/{job_id}/retry",
        "/debug/echo",
    )
    add(
        PermissionAction.ADMIN_WRITE,
        "PUT",
        "/firewall/chains/policy",
        "/users/{username}",
        "/users/{username}/keys",
        "/groups/{name}",
        "/backup/servers/{server_id}",
        "/backup/jobs/{job_id}",
    )
    add(
        PermissionAction.HOST_CONFIG_READ,
        "GET",
        "/proxy/configs/{domain}/advanced",
    )
    add(
        PermissionAction.HOST_CONFIG_WRITE,
        "PUT",
        "/proxy/configs/{domain}/advanced",
    )
    add(
        PermissionAction.ADMIN_WRITE,
        "DELETE",
        "/firewall/rules",
        "/users/{username}",
        "/groups/{name}",
        "/settings/customization/logo",
        "/settings/customization/banner",
        "/settings/api-tokens/{token_id}",
        "/backup/servers/{server_id}",
        "/backup/jobs/{job_id}",
        "/backup/instances/{instance_id}",
        "/ssh-keys/{key_name}",
        "/proxy/configs/{domain}",
        "/proxy/certificates/{domain}",
    )

    # Cluster information is shared by administrators and authenticated peers.
    add(PermissionAction.CLUSTER_INFO_READ, "GET", "/cluster/info")

    # Cluster routes used by authenticated administrators.
    add(
        PermissionAction.CLUSTER_READ,
        "GET",
        "/cluster/debug",
        "/cluster/nodes",
        "/cluster/load/distribution",
        "/cluster/load/recommendations",
        "/cluster/sync/rules",
        "/cluster/sync/status",
        "/cluster/containers/distribution",
        "/cluster/metrics/detailed",
        "/cluster/metrics/history",
        "/cluster/metrics/summary",
        "/cluster/alerts",
        "/cluster/health",
        "/cluster/replications",
        "/cluster/replications/{replication_id}/progress",
        "/cluster/nodes/{hostname}/resources",
        "/cluster/ha",
        "/cluster/ha/status",
    )
    add(
        PermissionAction.CLUSTER_WRITE,
        "POST",
        "/cluster/test-write",
        "/cluster/create",
        "/cluster/join",
        "/cluster/workload/placement",
        "/cluster/affinity",
        "/cluster/sync/rules",
        "/cluster/sync/execute",
        "/cluster/sync/migrate",
        "/cluster/alerts/{alert_id}/acknowledge",
        "/cluster/replications",
        "/cluster/replications/{replication_id}/trigger",
        "/cluster/keys/rotate",
        "/cluster/ha/enable",
        "/cluster/ha/disable",
        "/cluster/ha/failover",
        "/cluster/ha/vip/assign",
        "/cluster/ha/vip/release",
    )
    add(PermissionAction.CLUSTER_WRITE, "PUT", "/cluster/ha")
    add(
        PermissionAction.CLUSTER_WRITE,
        "DELETE",
        "/cluster/affinity/{service_id}",
        "/cluster/sync/rules/{service_name}",
        "/cluster/alerts/cleanup",
        "/cluster/replications/{replication_id}",
    )

    # Inter-node routes. Administrators may also call known internal routes, but
    # cluster principals receive no permissions beyond this list and inventory.
    add(
        PermissionAction.CLUSTER_INTERNAL_READ,
        "GET",
        "/cluster/node/metrics",
        "/cluster/download/{filename}",
        "/cluster/ha/vote",
        "/cluster/ha/config",
        "/cluster/jobs/{job_id}",
    )
    add(
        PermissionAction.CLUSTER_INTERNAL_WRITE,
        "POST",
        "/cluster/register",
        "/cluster/bootstrap",
        "/cluster/leave",
        "/cluster/force-leave",
        "/cluster/keys/update",
        "/cluster/export/{resource_type}/{resource_name}",
        "/cluster/upload",
        "/cluster/import/{resource_type}",
        "/cluster/ha/heartbeat",
        "/cluster/ha/master-update",
        "/cluster/ha/vip-owner-update",
        "/cluster/ha/config-sync",
    )
    add(
        PermissionAction.CLUSTER_INTERNAL_WRITE,
        "DELETE",
        "/cluster/nodes/{node_id}",
    )

    return MappingProxyType(policies)


ROUTE_POLICIES = _build_route_policies()


def _compile_route_template(path_template: str) -> Pattern[str]:
    """Compile a FastAPI-style path template to an anchored request regex."""

    parts: list[str] = []
    position = 0
    for match in re.finditer(r"{([^{}]+)}", path_template):
        parts.append(re.escape(path_template[position:match.start()]))
        parameter = match.group(1)
        converter = parameter.split(":", 1)[1] if ":" in parameter else ""
        parts.append(r".+" if converter == "path" else r"[^/]+")
        position = match.end()
    parts.append(re.escape(path_template[position:]))
    return re.compile(r"^" + "".join(parts) + r"/?$")


_COMPILED_ROUTE_POLICIES = tuple(
    (method, _compile_route_template(path), action)
    for (method, path), action in ROUTE_POLICIES.items()
)


def get_route_action(method: str, path: str) -> PermissionAction | None:
    """Return the action for an actual request path, or None if unknown."""

    normalized_method = method.upper()
    for policy_method, pattern, action in _COMPILED_ROUTE_POLICIES:
        if policy_method == normalized_method and pattern.fullmatch(path):
            return action
    return None


def has_route_policy(method: str, path_template: str) -> bool:
    """Return whether an exact method/route-template pair is registered."""

    return (method.upper(), path_template) in ROUTE_POLICIES


def is_public_request(method: str, path: str) -> bool:
    """Return whether a request may bypass authentication."""

    return get_route_action(method, path) == PermissionAction.PUBLIC


def get_user_groups(username: str) -> Set[str]:
    """Return all Linux groups to which username belongs."""

    if username in SYSTEM_PRINCIPALS or username.startswith("api-token:"):
        return set()
    try:
        pw = pwd.getpwnam(username)
        groups: Set[str] = set()
        for group in grp.getgrall():
            if username in group.gr_mem or group.gr_gid == pw.pw_gid:
                groups.add(group.gr_name)
        return groups
    except KeyError:
        return set()


def is_admin(username: str, groups: Set[str]) -> bool:
    """Return whether a user or API principal has administrator access."""

    try:
        if pwd.getpwnam(username).pw_uid == 0:
            return True
    except KeyError:
        pass
    return bool(groups & ADMIN_GROUPS)


def has_container_access(username: str, groups: Set[str]) -> bool:
    """Return whether the principal may manage containers."""

    return is_admin(username, groups) or bool(groups & CONTAINER_GROUPS)


def has_vm_access(username: str, groups: Set[str]) -> bool:
    """Return whether the principal may manage VMs, ISOs, and VM networks."""

    return is_admin(username, groups) or bool(groups & LIBVIRT_GROUPS)


def has_storage_access(username: str, groups: Set[str]) -> bool:
    """Return whether the principal may manage physical storage."""

    return is_admin(username, groups) or bool(groups & STORAGE_GROUPS)


def has_shell_access(username: str, groups: Set[str]) -> bool:
    """Return whether the principal may open a system shell."""

    return is_admin(username, groups) or bool(groups & SHELL_GROUPS)


def has_log_access(username: str, groups: Set[str]) -> bool:
    """Return whether the principal may read logs."""

    return is_admin(username, groups) or bool(groups & LOG_GROUPS)


def check_path_permission(
    username: str,
    groups: Set[str],
    path: str,
    method: str = "GET",
) -> bool:
    """Authorize a principal for one HTTP method and actual request path.

    Unknown methods and paths are denied before administrator checks so newly
    added or mistyped routes never inherit access accidentally.
    """

    action = get_route_action(method, path)
    if action is None:
        return False

    if action in {
        PermissionAction.PUBLIC,
        PermissionAction.AUTH_SELF,
        PermissionAction.SYSTEM_READ,
    }:
        return True

    if action in {
        PermissionAction.CLUSTER_INTERNAL_READ,
        PermissionAction.CLUSTER_INTERNAL_WRITE,
    }:
        return username in CLUSTER_PRINCIPALS

    if action == PermissionAction.CLUSTER_INFO_READ:
        return is_admin(username, groups) or username in CLUSTER_PRINCIPALS

    if is_admin(username, groups):
        return True

    if username in CLUSTER_PRINCIPALS:
        return action in {
            PermissionAction.CLUSTER_INTERNAL_READ,
            PermissionAction.CLUSTER_INTERNAL_WRITE,
            PermissionAction.CONTAINER_INVENTORY,
            PermissionAction.VM_INVENTORY,
        }

    if action in {
        PermissionAction.CONTAINER_INVENTORY,
        PermissionAction.CONTAINER_READ,
        PermissionAction.CONTAINER_WRITE,
    }:
        return bool(groups & CONTAINER_GROUPS)

    if action in {
        PermissionAction.VM_INVENTORY,
        PermissionAction.VM_READ,
        PermissionAction.VM_WRITE,
        PermissionAction.VM_NETWORK_READ,
        PermissionAction.VM_NETWORK_WRITE,
    }:
        return bool(groups & LIBVIRT_GROUPS)

    if action in {
        PermissionAction.STORAGE_READ,
        PermissionAction.STORAGE_WRITE,
    }:
        return bool(groups & STORAGE_GROUPS)

    if action == PermissionAction.LOG_READ:
        return bool(groups & LOG_GROUPS)

    return False


_TOKEN_OPERATOR_ACTIONS = {
    PermissionAction.AUTH_SELF,
    PermissionAction.SYSTEM_READ,
    PermissionAction.CONTAINER_INVENTORY,
    PermissionAction.CONTAINER_READ,
    PermissionAction.CONTAINER_WRITE,
    PermissionAction.VM_INVENTORY,
    PermissionAction.VM_READ,
    PermissionAction.VM_WRITE,
    PermissionAction.VM_NETWORK_READ,
    PermissionAction.VM_NETWORK_WRITE,
    PermissionAction.STORAGE_READ,
    PermissionAction.STORAGE_WRITE,
    PermissionAction.LOG_READ,
}

_TOKEN_READ_ONLY_ACTIONS = {
    PermissionAction.AUTH_SELF,
    PermissionAction.SYSTEM_READ,
    PermissionAction.CONTAINER_INVENTORY,
    PermissionAction.CONTAINER_READ,
    PermissionAction.VM_INVENTORY,
    PermissionAction.VM_READ,
    PermissionAction.VM_NETWORK_READ,
    PermissionAction.STORAGE_READ,
    PermissionAction.LOG_READ,
    PermissionAction.ADMIN_READ,
    PermissionAction.CLUSTER_READ,
    PermissionAction.CLUSTER_INFO_READ,
}


def api_token_scope_allows(scopes: Set[str] | frozenset[str], action: str) -> bool:
    """Match one permission action against exact or subsystem wildcard scopes."""

    if "*" in scopes or action in scopes:
        return True
    subsystem = action.split(":", 1)[0]
    return f"{subsystem}:*" in scopes


def check_api_token_permission(token, path: str, method: str = "GET") -> bool:
    """Apply both token role and token scope to an explicit route policy."""

    action = get_route_action(method, path)
    if action is None:
        return False
    if action in {
        PermissionAction.CLUSTER_INTERNAL_READ,
        PermissionAction.CLUSTER_INTERNAL_WRITE,
        PermissionAction.HOST_CONFIG_READ,
        PermissionAction.HOST_CONFIG_WRITE,
    }:
        return False
    role = getattr(token, "role", "")
    scopes = getattr(token, "scopes", frozenset())
    if role == "admin":
        role_allowed = True
    elif role == "operator":
        role_allowed = action in _TOKEN_OPERATOR_ACTIONS
    elif role == "read-only":
        role_allowed = action in _TOKEN_READ_ONLY_ACTIONS
    else:
        return False
    return role_allowed and api_token_scope_allows(scopes, action.value)


def check_api_token_capability(token, capability: str) -> bool:
    """Authorize a non-HTTP capability such as an interactive terminal."""

    role = getattr(token, "role", "")
    scopes = getattr(token, "scopes", frozenset())
    if role == "read-only":
        return False
    return api_token_scope_allows(scopes, capability)


def get_permission_summary(username: str, groups: Set[str]) -> dict:
    """Return a JSON-serializable summary of a principal's subsystem access."""

    return {
        "username": username,
        "groups": sorted(groups),
        "permissions": {
            "admin": is_admin(username, groups),
            "containers": has_container_access(username, groups),
            "vms": has_vm_access(username, groups),
            "storage": has_storage_access(username, groups),
            "shell": has_shell_access(username, groups),
            "logs": has_log_access(username, groups),
        },
    }
