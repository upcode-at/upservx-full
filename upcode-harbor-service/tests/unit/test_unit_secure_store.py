"""Tests for centralized owner-only configuration persistence."""

import json
import os
import stat

import pytest

from lib import secure_store


def _mode(path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_secure_writes_are_atomic_and_owner_only(tmp_path, monkeypatch):
    root = tmp_path / "etc" / "upcode-harbor"
    monkeypatch.setattr(secure_store, "CONFIG_ROOT", root)

    secure_store.secure_write_json("nested/settings.json", {"enabled": True})

    target = root / "nested" / "settings.json"
    assert json.loads(target.read_text()) == {"enabled": True}
    assert _mode(root) == 0o700
    assert _mode(root / "nested") == 0o700
    assert _mode(target) == 0o600
    assert list(target.parent.glob(f".{target.name}.*")) == []


def test_permission_enforcement_repairs_every_entry(tmp_path, monkeypatch):
    root = tmp_path / "upcode-harbor"
    nested = root / "nested"
    nested.mkdir(parents=True)
    config_file = nested / "config.json"
    config_file.write_text("{}")
    os.chmod(root, 0o755)
    os.chmod(nested, 0o777)
    os.chmod(config_file, 0o666)
    monkeypatch.setattr(secure_store, "CONFIG_ROOT", root)

    result = secure_store.enforce_config_permissions()

    assert result == {"files": 1, "directories": 2}
    assert _mode(root) == 0o700
    assert _mode(nested) == 0o700
    assert _mode(config_file) == 0o600


def test_corrupt_json_and_symlinks_fail_closed(tmp_path, monkeypatch):
    root = tmp_path / "upcode-harbor"
    root.mkdir()
    corrupt = root / "corrupt.json"
    corrupt.write_text("not-json")
    monkeypatch.setattr(secure_store, "CONFIG_ROOT", root)

    with pytest.raises(secure_store.SecureStoreError):
        secure_store.secure_read_json(corrupt)

    outside = tmp_path / "outside"
    outside.write_text("secret")
    (root / "linked-secret").symlink_to(outside)
    with pytest.raises(secure_store.SecureStoreError, match="Unsafe configuration link"):
        secure_store.enforce_config_permissions()


def test_configuration_root_must_not_be_a_symlink(tmp_path, monkeypatch):
    real_root = tmp_path / "real"
    real_root.mkdir()
    linked_root = tmp_path / "upcode-harbor"
    linked_root.symlink_to(real_root, target_is_directory=True)
    monkeypatch.setattr(secure_store, "CONFIG_ROOT", linked_root)

    with pytest.raises(secure_store.SecureStoreError, match="Unsafe configuration"):
        secure_store.ensure_config_directory()


def test_relative_paths_cannot_escape_the_configuration_root(tmp_path, monkeypatch):
    monkeypatch.setattr(secure_store, "CONFIG_ROOT", tmp_path / "upcode-harbor")

    with pytest.raises(secure_store.SecureStoreError, match="escapes"):
        secure_store.secure_write_json("../outside.json", {"secret": True})

    assert not (tmp_path / "outside.json").exists()
