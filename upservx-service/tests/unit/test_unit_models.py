"""
Unit tests for lib/models.py
==============================
Verifies Pydantic models for correct validation, default values, and
serialization. No external dependencies required.
"""

import pytest
from pydantic import ValidationError

from lib.models import (
    Container,
    ContainerCreate,
    ISOInfo,
    ISODownloadRequest,
    ContainerImageInfo,
    ImagePullRequest,
    DriveInfo,
    DriveMountRequest,
    DriveFormatRequest,
    SettingsModel,
    UserCreateModel,
    UserUpdateModel,
    GroupCreateModel,
    SSHKeyListModel,
    VirtualMachineCreate,
    BackupServerCreate,
    BackupJobCreate,
    FirewallRuleCreate,
    ProxyConfigCreate,
    NotificationConfig,
    NetworkSettingsModel,
)


# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------

class TestContainerModel:
    _valid = dict(
        id=1,
        name="web",
        type="docker",
        status="running",
        image="nginx:latest",
        cpu=0.5,
        memory=512,
        created="2025-01-01T00:00:00",
    )

    def test_valid_container(self):
        c = Container(**self._valid)
        assert c.name == "web"
        assert c.ports == []    # Default
        assert c.mounts == []
        assert c.envs == []

    def test_missing_required_field_raises(self):
        data = dict(self._valid)
        del data["image"]
        with pytest.raises(ValidationError):
            Container(**data)

    def test_ports_accepted(self):
        c = Container(**{**self._valid, "ports": ["8080:80"]})
        assert c.ports == ["8080:80"]


class TestContainerCreate:
    def test_defaults_populated(self):
        cc = ContainerCreate(name="test", type="docker", image="alpine")
        assert cc.cpu == 0.0
        assert cc.memory == 0
        assert cc.ports == []

    def test_required_fields(self):
        with pytest.raises(ValidationError):
            ContainerCreate(name="x")  # type and image missing


# ---------------------------------------------------------------------------
# ISO models
# ---------------------------------------------------------------------------

class TestISOInfo:
    def test_valid_iso_info(self):
        iso = ISOInfo(
            id=1,
            name="ubuntu-22.04.iso",
            size=1024.0,
            type="linux",
            version="22.04",
            architecture="x86_64",
            created="2025-01-01",
            used=False,
            path="/var/lib/isos/ubuntu.iso",
        )
        assert iso.used is False

    def test_missing_path_raises(self):
        with pytest.raises(ValidationError):
            ISOInfo(id=1, name="x", size=0.0, type="linux", version="1",
                    architecture="x64", created="2025", used=False)


class TestISODownloadRequest:
    def test_url_required(self):
        with pytest.raises(ValidationError):
            ISODownloadRequest()

    def test_name_optional(self):
        req = ISODownloadRequest(url="http://example.com/x.iso")
        assert req.name is None


# ---------------------------------------------------------------------------
# Image models
# ---------------------------------------------------------------------------

class TestContainerImageInfo:
    def test_defaults(self):
        img = ContainerImageInfo(
            id=1, repository="nginx", tag="latest",
            imageId="sha256:abc", size=200.0, created="2025-01-01",
        )
        assert img.used is False
        assert img.pulls == 0


class TestImagePullRequest:
    def test_defaults(self):
        req = ImagePullRequest(image="nginx:latest")
        assert req.type == "docker"
        assert req.registry is None


# ---------------------------------------------------------------------------
# Drive models
# ---------------------------------------------------------------------------

class TestDriveInfo:
    def test_valid_drive(self):
        d = DriveInfo(
            device="/dev/sda", name="SSD", type="ssd",
            size=500.0, used=100.0, available=400.0,
            filesystem="ext4", mountpoint="/mnt/ssd", mounted=True,
        )
        assert d.temperature is None  # optional

    def test_temperature_optional(self):
        d = DriveInfo(
            device="/dev/sda", name="SSD", type="ssd",
            size=500.0, used=100.0, available=400.0,
            filesystem="ext4", mountpoint="/mnt/ssd", mounted=True,
            temperature=45,
        )
        assert d.temperature == 45


class TestDriveMountRequest:
    def test_device_and_mountpoint_required(self):
        with pytest.raises(ValidationError):
            DriveMountRequest(device="/dev/sda")


class TestDriveFormatRequest:
    def test_label_optional(self):
        req = DriveFormatRequest(device="/dev/sdb", filesystem="ext4")
        assert req.label is None


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class TestSettingsModel:
    def test_defaults(self):
        s = SettingsModel(
            hostname="server01",
            timezone="Europe/Berlin",
            auto_updates=True,
            monitoring=True,
        )
        assert s.ssh_port == 22
        assert s.deny_root_login is False
        assert s.api_key is None

    def test_full_settings(self):
        s = SettingsModel(
            hostname="server01",
            timezone="UTC",
            auto_updates=False,
            monitoring=False,
            ssh_port=2222,
            deny_root_login=True,
            api_key="secret",
        )
        assert s.ssh_port == 2222
        assert s.deny_root_login is True


# ---------------------------------------------------------------------------
# User models
# ---------------------------------------------------------------------------

class TestUserCreateModel:
    def test_defaults(self):
        u = UserCreateModel(username="alice", password="pw123")
        assert u.groups == []
        assert u.shell == "/bin/bash"

    def test_username_and_password_required(self):
        with pytest.raises(ValidationError):
            UserCreateModel(username="alice")


class TestUserUpdateModel:
    def test_all_optional(self):
        u = UserUpdateModel()
        assert u.groups is None
        assert u.shell is None


class TestGroupCreateModel:
    def test_members_optional(self):
        g = GroupCreateModel(name="devs")
        assert g.members == []


class TestSSHKeyListModel:
    def test_empty_default(self):
        m = SSHKeyListModel()
        assert m.keys == []

    def test_keys_accepted(self):
        m = SSHKeyListModel(keys=["ssh-rsa AAAA... user@host"])
        assert len(m.keys) == 1


# ---------------------------------------------------------------------------
# VirtualMachineCreate
# ---------------------------------------------------------------------------

class TestVirtualMachineCreate:
    def test_defaults(self):
        vm = VirtualMachineCreate(
            name="myvm", cpu=2, memory=2048, iso="ubuntu.iso"
        )
        assert vm.network_mode == "nat"
        assert vm.autostart is False
        assert vm.disks == []

    def test_required_fields(self):
        with pytest.raises(ValidationError):
            VirtualMachineCreate(name="x", cpu=2)          # memory and iso missing


# ---------------------------------------------------------------------------
# BackupServerCreate
# ---------------------------------------------------------------------------

class TestBackupServerCreate:
    def test_defaults(self):
        b = BackupServerCreate(name="local-backup", type="local")
        assert b.port == 22
        assert b.remote_path == "/backups"

    def test_remote_server(self):
        b = BackupServerCreate(
            name="remote", type="remote",
            host="backup.example.com", port=22,
            remote_path="/backups", auth_type="password",
            username="admin", password="secret",
        )
        assert b.host == "backup.example.com"


# ---------------------------------------------------------------------------
# BackupJobCreate
# ---------------------------------------------------------------------------

class TestBackupJobCreate:
    def test_valid(self):
        j = BackupJobCreate(
            name="nightly",
            backup_type="vm",
            targets=["myvm"],
            schedule="0 2 * * *",
            server_id=1,
        )
        assert j.retention_days == 30
        assert j.compression is True


# ---------------------------------------------------------------------------
# FirewallRuleCreate
# ---------------------------------------------------------------------------

class TestFirewallRuleCreate:
    def test_defaults(self):
        r = FirewallRuleCreate(chain="input")
        assert r.action == "accept"
        assert r.protocol is None

    def test_full_rule(self):
        r = FirewallRuleCreate(
            chain="input", protocol="tcp", port=443,
            source_ip="192.168.1.0/24", action="accept",
            comment="Allow HTTPS",
        )
        assert r.port == 443


# ---------------------------------------------------------------------------
# ProxyConfigCreate
# ---------------------------------------------------------------------------

class TestProxyConfigCreate:
    def test_defaults(self):
        p = ProxyConfigCreate(domain="app.example.com")
        assert p.backend_port == 9500
        assert p.ssl_enabled is False

    def test_domain_required(self):
        with pytest.raises(ValidationError):
            ProxyConfigCreate()


# ---------------------------------------------------------------------------
# NotificationConfig
# ---------------------------------------------------------------------------

class TestNotificationConfig:
    def test_all_defaults(self):
        cfg = NotificationConfig()
        assert cfg.email.enabled is False
        assert cfg.webhook.enabled is False
        assert cfg.events.container_create is True
        assert cfg.events.backup_failure is True


# ---------------------------------------------------------------------------
# NetworkSettings
# ---------------------------------------------------------------------------

class TestNetworkSettingsModel:
    def test_defaults(self):
        ns = NetworkSettingsModel()
        assert ns.dns_primary == "8.8.8.8"
        assert ns.dns_secondary == "8.8.4.4"

    def test_custom_dns(self):
        ns = NetworkSettingsModel(dns_primary="1.1.1.1", dns_secondary="1.0.0.1")
        assert ns.dns_primary == "1.1.1.1"
