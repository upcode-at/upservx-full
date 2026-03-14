"""
Unit-Tests für lib/permissions.py
====================================
Prüft alle Berechtigungslogiken isoliert.
Kein echter PAM-/Systemaufruf – pwd/grp werden gemockt.
"""

import sys
import types
import pytest
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Stub pwd und grp, damit Tests auch ohne entsprechende Benutzer laufen
# ---------------------------------------------------------------------------

_mock_pw = MagicMock()
_mock_pw.pw_uid = 1000
_mock_pw.pw_gid = 1000

_mock_grp_docker = MagicMock()
_mock_grp_docker.gr_name = "docker"
_mock_grp_docker.gr_gid = 998
_mock_grp_docker.gr_mem = ["testuser"]

_mock_grp_sudo = MagicMock()
_mock_grp_sudo.gr_name = "sudo"
_mock_grp_sudo.gr_gid = 27
_mock_grp_sudo.gr_mem = ["adminuser"]

_mock_grp_users = MagicMock()
_mock_grp_users.gr_name = "users"
_mock_grp_users.gr_gid = 100
_mock_grp_users.gr_mem = []


from lib.permissions import (  # noqa: E402
    is_admin,
    has_container_access,
    has_vm_access,
    has_storage_access,
    has_shell_access,
    has_log_access,
    check_path_permission,
    get_permission_summary,
    SYSTEM_PRINCIPALS,
)


# ---------------------------------------------------------------------------
# Hilfswerte
# ---------------------------------------------------------------------------

ADMIN_GROUPS = {"sudo"}
DOCKER_GROUPS = {"docker"}
LXD_GROUPS = {"lxd"}
LIBVIRT_GROUPS = {"libvirt"}
STORAGE_GROUPS = {"disk"}
SHELL_GROUPS = {"tty"}
LOG_GROUPS = {"adm"}
NO_GROUPS: set = set()


# ---------------------------------------------------------------------------
# is_admin
# ---------------------------------------------------------------------------

class TestIsAdmin:
    def test_sudo_group_is_admin(self):
        assert is_admin("alice", {"sudo"}) is True

    def test_wheel_group_is_admin(self):
        assert is_admin("alice", {"wheel"}) is True

    def test_no_group_is_not_admin(self):
        with patch("lib.permissions.pwd.getpwnam", side_effect=KeyError):
            assert is_admin("alice", set()) is False

    def test_system_principal_is_admin(self):
        for principal in SYSTEM_PRINCIPALS:
            assert is_admin(principal, set()) is True

    def test_uid_zero_is_admin(self):
        mock_pw = MagicMock()
        mock_pw.pw_uid = 0
        with patch("lib.permissions.pwd.getpwnam", return_value=mock_pw):
            assert is_admin("root", set()) is True


# ---------------------------------------------------------------------------
# Containerzugriff
# ---------------------------------------------------------------------------

class TestHasContainerAccess:
    def test_docker_group_has_access(self):
        assert has_container_access("user", {"docker"}) is True

    def test_lxd_group_has_access(self):
        assert has_container_access("user", {"lxd"}) is True

    def test_no_group_denied(self):
        with patch("lib.permissions.pwd.getpwnam", side_effect=KeyError):
            assert has_container_access("user", set()) is False

    def test_admin_has_container_access(self):
        assert has_container_access("admin", {"sudo"}) is True


# ---------------------------------------------------------------------------
# VM-Zugriff
# ---------------------------------------------------------------------------

class TestHasVmAccess:
    def test_libvirt_group_has_access(self):
        assert has_vm_access("user", {"libvirt"}) is True

    def test_kvm_group_has_access(self):
        assert has_vm_access("user", {"kvm"}) is True

    def test_docker_group_denied(self):
        with patch("lib.permissions.pwd.getpwnam", side_effect=KeyError):
            assert has_vm_access("user", {"docker"}) is False


# ---------------------------------------------------------------------------
# Storage-Zugriff
# ---------------------------------------------------------------------------

class TestHasStorageAccess:
    def test_disk_group_has_access(self):
        assert has_storage_access("user", {"disk"}) is True

    def test_storage_group_has_access(self):
        assert has_storage_access("user", {"storage"}) is True

    def test_no_group_denied(self):
        with patch("lib.permissions.pwd.getpwnam", side_effect=KeyError):
            assert has_storage_access("user", set()) is False


# ---------------------------------------------------------------------------
# Shell-Zugriff
# ---------------------------------------------------------------------------

class TestHasShellAccess:
    def test_tty_group_has_access(self):
        assert has_shell_access("user", {"tty"}) is True

    def test_admin_has_shell_access(self):
        assert has_shell_access("admin", {"sudo"}) is True

    def test_docker_only_denied(self):
        with patch("lib.permissions.pwd.getpwnam", side_effect=KeyError):
            assert has_shell_access("user", {"docker"}) is False


# ---------------------------------------------------------------------------
# Check_path_permission (Routing-Tabelle)
# ---------------------------------------------------------------------------

class TestCheckPathPermission:
    """check_path_permission folgt hierarchischen Präfixen."""

    def _admin(self):
        return {"sudo"}

    def _user(self):
        return set()

    # Container-Pfade
    def test_containers_path_allowed_for_docker_group(self):
        assert check_path_permission("u", {"docker"}, "/containers") is True

    def test_containers_path_denied_without_group(self):
        with patch("lib.permissions.pwd.getpwnam", side_effect=KeyError):
            assert check_path_permission("u", set(), "/containers") is False

    # VM-Pfade
    def test_vms_path_allowed_for_libvirt(self):
        assert check_path_permission("u", {"libvirt"}, "/vms") is True

    def test_vms_path_denied_for_docker_only(self):
        with patch("lib.permissions.pwd.getpwnam", side_effect=KeyError):
            assert check_path_permission("u", {"docker"}, "/vms") is False

    # Admin-Pfade
    def test_firewall_requires_admin(self):
        with patch("lib.permissions.pwd.getpwnam", side_effect=KeyError):
            assert check_path_permission("u", {"docker"}, "/firewall") is False
        assert check_path_permission("admin", {"sudo"}, "/firewall") is True

    def test_users_requires_admin(self):
        with patch("lib.permissions.pwd.getpwnam", side_effect=KeyError):
            assert check_path_permission("u", {"docker"}, "/users") is False

    # Öffentliche Pfade
    def test_root_path_always_allowed(self):
        with patch("lib.permissions.pwd.getpwnam", side_effect=KeyError):
            assert check_path_permission("u", set(), "/") is True

    def test_auth_path_always_allowed(self):
        with patch("lib.permissions.pwd.getpwnam", side_effect=KeyError):
            assert check_path_permission("u", set(), "/auth/login") is True

    # Log-Pfade
    def test_logs_allowed_for_adm_group(self):
        assert check_path_permission("u", {"adm"}, "/logs") is True

    def test_logs_denied_without_group(self):
        with patch("lib.permissions.pwd.getpwnam", side_effect=KeyError):
            assert check_path_permission("u", set(), "/logs") is False

    # Storage
    def test_drives_allowed_for_disk_group(self):
        assert check_path_permission("u", {"disk"}, "/drives") is True


# ---------------------------------------------------------------------------
# get_permission_summary
# ---------------------------------------------------------------------------

class TestGetPermissionSummary:
    def test_returns_complete_structure(self):
        summary = get_permission_summary("admin", {"sudo"})
        assert summary["username"] == "admin"
        assert "groups" in summary
        assert "permissions" in summary
        perms = summary["permissions"]
        assert set(perms.keys()) == {"admin", "containers", "vms", "storage", "shell", "logs"}

    def test_admin_has_all_perms(self):
        summary = get_permission_summary("admin", {"sudo"})
        assert all(summary["permissions"].values())

    def test_unprivileged_has_no_perms(self):
        with patch("lib.permissions.pwd.getpwnam", side_effect=KeyError):
            summary = get_permission_summary("guest", set())
        assert not any(summary["permissions"].values())

    def test_docker_user_permissions(self):
        with patch("lib.permissions.pwd.getpwnam", side_effect=KeyError):
            summary = get_permission_summary("dev", {"docker"})
        assert summary["permissions"]["containers"] is True
        assert summary["permissions"]["admin"] is False
        assert summary["permissions"]["vms"] is False
