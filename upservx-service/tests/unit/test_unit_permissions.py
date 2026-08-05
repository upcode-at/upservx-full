"""Unit tests for the deny-by-default authorization policy."""

from unittest.mock import MagicMock, patch

import pytest

from lib.permissions import (
    API_PRINCIPALS,
    CLUSTER_PRINCIPALS,
    PermissionAction,
    ROUTE_POLICIES,
    check_path_permission,
    get_permission_summary,
    get_route_action,
    get_user_groups,
    has_container_access,
    has_log_access,
    has_route_policy,
    has_shell_access,
    has_storage_access,
    has_vm_access,
    is_admin,
    is_public_request,
)


class TestGroupResolution:
    def test_system_principals_do_not_use_linux_accounts(self):
        with (
            patch("lib.permissions.pwd.getpwnam") as getpwnam,
            patch("lib.permissions.grp.getgrall") as getgrall,
        ):
            for principal in API_PRINCIPALS | CLUSTER_PRINCIPALS:
                assert get_user_groups(principal) == set()
        getpwnam.assert_not_called()
        getgrall.assert_not_called()

    def test_primary_and_supplementary_groups_are_resolved(self):
        user = MagicMock(pw_gid=1000)
        primary = MagicMock(gr_name="users", gr_gid=1000, gr_mem=[])
        supplementary = MagicMock(gr_name="docker", gr_gid=998, gr_mem=["alice"])
        unrelated = MagicMock(gr_name="adm", gr_gid=4, gr_mem=["bob"])
        with (
            patch("lib.permissions.pwd.getpwnam", return_value=user),
            patch(
                "lib.permissions.grp.getgrall",
                return_value=[primary, supplementary, unrelated],
            ),
        ):
            assert get_user_groups("alice") == {"users", "docker"}

    def test_unknown_linux_user_has_no_groups(self):
        with patch("lib.permissions.pwd.getpwnam", side_effect=KeyError):
            assert get_user_groups("missing") == set()


class TestRolePredicates:
    @pytest.mark.parametrize("group", ["sudo", "wheel", "root"])
    def test_admin_groups_are_administrators(self, group):
        assert is_admin("alice", {group}) is True

    def test_uid_zero_is_an_administrator(self):
        account = MagicMock(pw_uid=0)
        with patch("lib.permissions.pwd.getpwnam", return_value=account):
            assert is_admin("root", set()) is True

    def test_legacy_api_key_principal_is_not_an_administrator(self):
        with patch("lib.permissions.pwd.getpwnam", side_effect=KeyError):
            assert is_admin("api-key", set()) is False

    @pytest.mark.parametrize("principal", ["cluster-node", "cluster-master"])
    def test_cluster_principals_are_not_administrators(self, principal):
        with patch("lib.permissions.pwd.getpwnam", side_effect=KeyError):
            assert is_admin(principal, set()) is False

    @pytest.mark.parametrize("group", ["docker", "lxd", "lxc"])
    def test_container_roles(self, group):
        assert has_container_access("operator", {group}) is True
        assert has_vm_access("operator", {group}) is False

    @pytest.mark.parametrize("group", ["libvirt", "kvm"])
    def test_vm_roles(self, group):
        assert has_vm_access("operator", {group}) is True
        assert has_container_access("operator", {group}) is False

    @pytest.mark.parametrize("group", ["disk", "storage"])
    def test_storage_roles(self, group):
        assert has_storage_access("operator", {group}) is True

    def test_shell_role(self):
        assert has_shell_access("operator", {"tty"}) is True

    @pytest.mark.parametrize("group", ["adm", "log"])
    def test_log_roles(self, group):
        assert has_log_access("operator", {group}) is True


class TestRoutePolicy:
    def test_policy_contains_explicit_read_and_write_actions(self):
        assert get_route_action("GET", "/security/packages") == PermissionAction.ADMIN_READ
        assert (
            get_route_action("POST", "/security/packages/upgrade")
            == PermissionAction.ADMIN_WRITE
        )
        assert get_route_action("GET", "/vm-networks") == PermissionAction.VM_NETWORK_READ
        assert (
            get_route_action("POST", "/vm-networks")
            == PermissionAction.VM_NETWORK_WRITE
        )
        assert (
            get_route_action("POST", "/cluster/keys/rotate")
            == PermissionAction.CLUSTER_WRITE
        )
        assert (
            get_route_action("POST", "/cluster/keys/update")
            == PermissionAction.CLUSTER_INTERNAL_WRITE
        )
        assert get_route_action("GET", "/jobs/job-id") == PermissionAction.ADMIN_READ
        assert (
            get_route_action("POST", "/jobs/job-id/cancel")
            == PermissionAction.ADMIN_WRITE
        )
        assert (
            get_route_action("GET", "/cluster/jobs/job-id")
            == PermissionAction.CLUSTER_INTERNAL_READ
        )

    def test_dynamic_route_templates_match_actual_paths(self):
        assert (
            get_route_action("POST", "/security/packages/upgrade/openssl")
            == PermissionAction.ADMIN_WRITE
        )
        assert (
            get_route_action("GET", "/logs/samba/archive/server.log")
            == PermissionAction.LOG_READ
        )

    def test_paths_are_anchored_instead_of_prefix_matched(self):
        assert get_route_action("GET", "/security-archive/packages") is None
        assert get_route_action("GET", "/containers-extra") is None

    def test_http_method_is_part_of_the_policy(self):
        assert get_route_action("GET", "/security/packages/upgrade") is None
        assert get_route_action("DELETE", "/cluster/create") is None

    def test_public_routes_require_an_exact_method_and_path(self):
        assert is_public_request("POST", "/auth/login") is True
        assert is_public_request("GET", "/auth/login") is False
        assert is_public_request("GET", "/settings/customization/logo/file") is True
        assert is_public_request("GET", "/settings/customization/private") is False

    def test_policy_is_immutable(self):
        with pytest.raises(TypeError):
            ROUTE_POLICIES[("GET", "/new-route")] = PermissionAction.SYSTEM_READ

    def test_exact_policy_lookup_uses_route_templates(self):
        assert has_route_policy("GET", "/vms/{name}/snapshots") is True
        assert has_route_policy("GET", "/vms/demo/snapshots") is False


class TestDenyByDefault:
    @pytest.mark.parametrize(
        ("username", "groups"),
        [
            ("guest", set()),
            ("container-operator", {"docker"}),
            ("vm-operator", {"libvirt"}),
            ("storage-operator", {"disk"}),
            ("log-reader", {"adm"}),
            ("shell-user", {"tty"}),
            ("administrator", {"sudo"}),
            ("api-key", set()),
            ("cluster-node", set()),
            ("cluster-master", set()),
        ],
    )
    def test_unknown_routes_are_denied_for_every_principal(self, username, groups):
        with patch("lib.permissions.pwd.getpwnam", side_effect=KeyError):
            assert check_path_permission(username, groups, "/not-registered", "GET") is False

    @pytest.mark.parametrize(
        ("username", "groups"),
        [
            ("guest", set()),
            ("container-operator", {"docker"}),
            ("vm-operator", {"libvirt"}),
            ("storage-operator", {"disk"}),
            ("log-reader", {"adm"}),
            ("shell-user", {"tty"}),
            ("cluster-node", set()),
            ("cluster-master", set()),
        ],
    )
    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/security/packages"),
            ("POST", "/security/packages/upgrade"),
            ("GET", "/cluster/nodes"),
            ("POST", "/cluster/create"),
            ("POST", "/cluster/ha/failover"),
        ],
    )
    def test_non_admin_roles_cannot_access_admin_routes(
        self,
        username,
        groups,
        method,
        path,
    ):
        with patch("lib.permissions.pwd.getpwnam", side_effect=KeyError):
            assert check_path_permission(username, groups, path, method) is False

    @pytest.mark.parametrize("group", ["docker", "lxd", "lxc"])
    def test_container_roles_cannot_cross_into_vm_or_host_admin(self, group):
        assert check_path_permission("operator", {group}, "/containers", "GET") is True
        assert check_path_permission("operator", {group}, "/containers", "POST") is True
        assert check_path_permission("operator", {group}, "/vms", "GET") is False
        assert check_path_permission("operator", {group}, "/security/packages", "GET") is False

    @pytest.mark.parametrize("group", ["libvirt", "kvm"])
    def test_vm_roles_can_manage_vm_networks_but_not_host_networks(self, group):
        assert check_path_permission("operator", {group}, "/vm-networks", "GET") is True
        assert check_path_permission("operator", {group}, "/vm-networks", "POST") is True
        assert check_path_permission("operator", {group}, "/network/settings", "GET") is False
        assert check_path_permission("operator", {group}, "/cluster/create", "POST") is False

    @pytest.mark.parametrize("group", ["disk", "storage"])
    def test_storage_roles_are_limited_to_storage_routes(self, group):
        assert check_path_permission("operator", {group}, "/drives", "GET") is True
        assert check_path_permission("operator", {group}, "/drives/format", "POST") is True
        assert check_path_permission("operator", {group}, "/backup/jobs", "GET") is False

    @pytest.mark.parametrize("group", ["adm", "log"])
    def test_log_roles_are_read_only_and_limited_to_logs(self, group):
        assert check_path_permission("reader", {group}, "/logs", "GET") is True
        assert check_path_permission("reader", {group}, "/logs/app.log", "GET") is True
        assert check_path_permission("reader", {group}, "/services", "GET") is False
        assert check_path_permission("reader", {group}, "/logs", "DELETE") is False

    def test_tty_role_does_not_inherit_unregistered_shell_or_admin_routes(self):
        assert check_path_permission("shell", {"tty"}, "/system/shell", "POST") is False
        assert check_path_permission("shell", {"tty"}, "/security/packages", "GET") is False


class TestSystemPrincipals:
    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/security/packages"),
            ("POST", "/security/packages/upgrade"),
            ("GET", "/cluster/nodes"),
            ("POST", "/cluster/create"),
            ("POST", "/vm-networks"),
        ],
    )
    def test_legacy_api_key_principal_cannot_access_admin_routes(self, method, path):
        with patch("lib.permissions.pwd.getpwnam", side_effect=KeyError):
            assert check_path_permission("api-key", set(), path, method) is False

    @pytest.mark.parametrize("principal", ["administrator", "api-key"])
    def test_non_cluster_principals_cannot_access_internal_routes(self, principal):
        groups = {"sudo"} if principal == "administrator" else set()
        with patch("lib.permissions.pwd.getpwnam", side_effect=KeyError):
            assert check_path_permission(
                principal,
                groups,
                "/cluster/ha/heartbeat",
                "POST",
            ) is False

    @pytest.mark.parametrize("principal", ["cluster-node", "cluster-master"])
    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/cluster/node/metrics"),
            ("GET", "/cluster/info"),
            ("POST", "/cluster/ha/heartbeat"),
            ("POST", "/cluster/keys/update"),
            ("POST", "/cluster/export/container/demo"),
            ("GET", "/containers"),
            ("GET", "/vms"),
        ],
    )
    def test_cluster_principals_can_access_only_required_inter_node_routes(
        self,
        principal,
        method,
        path,
    ):
        assert check_path_permission(principal, set(), path, method) is True

    @pytest.mark.parametrize("principal", ["cluster-node", "cluster-master"])
    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/security/packages"),
            ("POST", "/security/packages/upgrade"),
            ("POST", "/containers"),
            ("POST", "/vms"),
            ("GET", "/cluster/nodes"),
            ("POST", "/cluster/create"),
            ("POST", "/cluster/ha/failover"),
            ("POST", "/cluster/keys/rotate"),
            ("GET", "/containers/demo/logs"),
        ],
    )
    def test_cluster_principals_cannot_use_user_or_admin_operations(
        self,
        principal,
        method,
        path,
    ):
        with patch("lib.permissions.pwd.getpwnam", side_effect=KeyError):
            assert check_path_permission(principal, set(), path, method) is False


class TestPermissionSummary:
    def test_summary_shape_remains_backwards_compatible(self):
        summary = get_permission_summary("admin", {"sudo"})
        assert summary["username"] == "admin"
        assert summary["groups"] == ["sudo"]
        assert set(summary["permissions"]) == {
            "admin",
            "containers",
            "vms",
            "storage",
            "shell",
            "logs",
        }
        assert all(summary["permissions"].values())

    def test_unprivileged_user_has_no_subsystem_permissions(self):
        with patch("lib.permissions.pwd.getpwnam", side_effect=KeyError):
            summary = get_permission_summary("guest", set())
        assert not any(summary["permissions"].values())
