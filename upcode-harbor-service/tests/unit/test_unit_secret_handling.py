"""Regression tests for fail-closed credential storage and redaction."""

import json

import pytest

from handlers.backup import BackupManager
from lib import config_manager
from lib.encryption import EncryptionManager


@pytest.fixture()
def backup_config(tmp_path, monkeypatch):
    config_root = tmp_path / "upcode-harbor"
    monkeypatch.setattr(config_manager, "CONFIG_DIR", str(config_root))
    monkeypatch.setattr(config_manager, "BACKUP_DIR", str(config_root / "backup"))
    monkeypatch.setattr(
        config_manager,
        "BACKUP_SERVERS_FILE",
        str(config_root / "backup" / "backup_servers.json"),
    )
    monkeypatch.setattr(config_manager, "SSH_KEYS_DIR", str(config_root / "ssh_keys"))
    monkeypatch.setattr(
        EncryptionManager, "KEY_FILE", str(config_root / "encryption.key")
    )
    manager = EncryptionManager()
    monkeypatch.setattr(config_manager, "get_encryption_manager", lambda: manager)
    return config_manager.ConfigManager(), config_root


def test_backup_password_is_encrypted_hidden_and_not_logged(backup_config, capsys):
    manager, config_root = backup_config
    plaintext = "uniquely-sensitive-password"

    created = manager.add_backup_server(
        {
            "name": "remote",
            "type": "remote",
            "auth_type": "password",
            "username": "alice",
            "password": plaintext,
        }
    )
    raw = (config_root / "backup" / "backup.db").read_bytes()

    assert plaintext.encode() not in raw
    assert plaintext not in capsys.readouterr().out
    assert "password_encrypted" not in created
    assert "password_encrypted" not in manager.get_backup_server(created["id"])
    assert (
        manager.get_backup_server(created["id"], include_secret=True)["password"]
        == plaintext
    )


def test_encryption_failure_never_stores_plaintext(backup_config, monkeypatch):
    manager, config_root = backup_config

    class BrokenEncryption:
        def encrypt(self, _value):
            raise RuntimeError("encryption unavailable")

    monkeypatch.setattr(
        config_manager, "get_encryption_manager", lambda: BrokenEncryption()
    )
    with pytest.raises(RuntimeError, match="encryption unavailable"):
        manager.add_backup_server(
            {"name": "remote", "type": "remote", "password": "do-not-store"}
        )

    path = config_root / "backup" / "backup.db"
    assert not path.exists() or b"do-not-store" not in path.read_bytes()


def test_plaintext_legacy_backup_password_is_never_returned(backup_config):
    manager, config_root = backup_config
    path = config_root / "backup" / "backup_servers.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"servers": [{
            "id": 1,
            "name": "legacy",
            "type": "local",
            "password": "legacy-plaintext",
        }]})
    )

    assert "password_encrypted" not in manager.get_backup_server(1)
    assert "password" not in manager.get_backup_server(1, include_secret=True)


def test_backup_encryption_helpers_fail_closed(monkeypatch):
    class BrokenEncryption:
        def encrypt(self, _value):
            raise RuntimeError("unavailable")

        def decrypt(self, _value):
            raise ValueError("unavailable")

    monkeypatch.setattr(
        "handlers.backup.get_encryption_manager", lambda: BrokenEncryption()
    )
    manager = BackupManager()

    with pytest.raises(RuntimeError, match="Failed to encrypt"):
        manager.encrypt_sensitive_data("secret")
    with pytest.raises(ValueError, match="Failed to decrypt"):
        manager.decrypt_sensitive_data("secret")
