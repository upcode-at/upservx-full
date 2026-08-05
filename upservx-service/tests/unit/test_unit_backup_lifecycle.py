"""Backup persistence, archive safety, and compression regressions."""

import io
import json
import base64
import tarfile
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from handlers.backup import BackupManager
from lib import encryption
from lib.backup_db import BackupDatabase


def test_legacy_json_servers_are_imported_into_sqlite(tmp_path):
    legacy = tmp_path / "backup_servers.json"
    legacy.write_text(json.dumps({
        "servers": [{
            "id": 7,
            "name": "legacy",
            "type": "local",
            "status": "active",
            "local_path": "/backup",
            "created": "2026-01-01T00:00:00",
        }]
    }))
    database = BackupDatabase(str(tmp_path / "backup.db"), str(legacy))

    server = database.get_backup_server(7)
    assert server["name"] == "legacy"
    assert server["status"] == "disconnected"
    assert not legacy.exists()
    assert (tmp_path / "backup_servers.json.migrated").exists()


def test_legacy_server_id_collision_does_not_discard_either_server(tmp_path):
    database_path = tmp_path / "backup.db"
    database = BackupDatabase(str(database_path), str(tmp_path / "missing.json"))
    database.create_backup_server(
        {"name": "sqlite", "type": "local", "local_path": "/sqlite"}
    )
    legacy = tmp_path / "backup_servers.json"
    legacy.write_text(json.dumps({
        "servers": [{
            "id": 1,
            "name": "json",
            "type": "local",
            "local_path": "/json",
        }]
    }))

    migrated = BackupDatabase(str(database_path), str(legacy))
    assert {server["name"] for server in migrated.get_backup_servers()} == {
        "sqlite", "json"
    }


def test_legacy_sqlite_credentials_are_reencrypted_with_canonical_key(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "backup.db"
    database = BackupDatabase(str(database_path), str(tmp_path / "missing.json"))
    server_id = database.create_backup_server(
        {"name": "remote", "type": "remote", "remote_path": "/backups"}
    )
    legacy_key = Fernet.generate_key()
    (tmp_path / "backup_key").write_bytes(legacy_key)
    legacy_ciphertext = base64.b64encode(
        Fernet(legacy_key).encrypt(b"legacy-secret")
    ).decode()
    with database.get_connection() as connection:
        connection.execute(
            "UPDATE backup_servers SET password_encrypted = ? WHERE id = ?",
            (legacy_ciphertext, server_id),
        )
        connection.execute(
            "DELETE FROM backup_metadata WHERE key = 'legacy_backup_cipher_migrated'"
        )
        connection.commit()

    monkeypatch.setattr(
        encryption.EncryptionManager, "KEY_FILE", str(tmp_path / "encryption.key")
    )
    monkeypatch.setattr(encryption, "_encryption_manager", None)
    migrated = BackupDatabase(str(database_path), str(tmp_path / "missing.json"))
    ciphertext = migrated.get_backup_server(
        server_id, include_secrets=True
    )["password_encrypted"]
    assert encryption.get_encryption_manager().decrypt(ciphertext) == "legacy-secret"
    assert ciphertext != legacy_ciphertext


@pytest.mark.parametrize("member_name", ["../../escape", "/absolute/path"])
def test_safe_restore_rejects_traversal(tmp_path, member_name):
    archive_path = tmp_path / "bad.tar"
    with tarfile.open(archive_path, "w") as archive:
        member = tarfile.TarInfo(member_name)
        member.size = 1
        archive.addfile(member, io.BytesIO(b"x"))

    with pytest.raises(ValueError):
        BackupManager.safe_extract_archive(str(archive_path), str(tmp_path / "restore"))


def test_safe_restore_rejects_links_and_overwrite(tmp_path):
    archive_path = tmp_path / "link.tar"
    with tarfile.open(archive_path, "w") as archive:
        member = tarfile.TarInfo("link")
        member.type = tarfile.SYMTYPE
        member.linkname = "/etc/passwd"
        archive.addfile(member)
    with pytest.raises(ValueError, match="links"):
        BackupManager.safe_extract_archive(str(archive_path), str(tmp_path / "restore"))

    good_path = tmp_path / "good.tar"
    with tarfile.open(good_path, "w") as archive:
        member = tarfile.TarInfo("file.txt")
        member.size = 1
        archive.addfile(member, io.BytesIO(b"x"))
    destination = tmp_path / "destination"
    destination.mkdir()
    (destination / "file.txt").write_text("existing")
    with pytest.raises(FileExistsError):
        BackupManager.safe_extract_archive(str(good_path), str(destination))
    assert (destination / "file.txt").read_text() == "existing"


def test_safe_restore_rejects_archive_file_used_as_parent(tmp_path):
    archive_path = tmp_path / "conflicting.tar"
    with tarfile.open(archive_path, "w") as archive:
        parent = tarfile.TarInfo("parent")
        parent.size = 1
        archive.addfile(parent, io.BytesIO(b"x"))
        child = tarfile.TarInfo("parent/child")
        child.size = 1
        archive.addfile(child, io.BytesIO(b"y"))

    destination = tmp_path / "restore"
    with pytest.raises(ValueError, match="used as a directory"):
        BackupManager.safe_extract_archive(str(archive_path), str(destination))
    assert not (destination / "parent").exists()


def test_archive_deletion_cannot_escape_configured_destination(tmp_path):
    outside = tmp_path / "outside.tar"
    outside.write_bytes(b"not an archive")
    configured = tmp_path / "destination"
    configured.mkdir()
    manager = BackupManager()

    with pytest.raises(ValueError, match="outside"):
        manager.delete_instance_archive(
            {"backup_path": str(outside)},
            {"type": "local", "local_path": str(configured)},
        )
    assert outside.exists()


def test_production_archive_respects_compression_and_has_checksum(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("backup data" * 100)
    manager = BackupManager.__new__(BackupManager)

    for compressed in (False, True):
        suffix = ".tar.gz" if compressed else ".tar"
        destination = tmp_path / f"archive{suffix}"
        success, result = manager._create_local_tar_backup(
            {"targets": [str(source)], "compression": compressed},
            str(destination),
            __import__("datetime").datetime.now(),
        )
        assert success is True
        assert len(result["checksum_sha256"]) == 64
        assert result["integrity_status"] == "verified"
        with open(destination, "rb") as handle:
            magic = handle.read(2)
        assert (magic == b"\x1f\x8b") is compressed


def test_running_vm_backup_uses_quiesced_snapshot_not_suspend():
    source = Path(__file__).resolve().parents[2] / "handlers" / "backup.py"
    implementation = source.read_text()
    assert '"snapshot-create-as"' in implementation
    assert '"--quiesce"' in implementation
    assert '"blockcommit"' in implementation
    assert '["virsh", "suspend"' not in implementation
