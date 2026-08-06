"""HA state must remain consistent across API and TLS processes."""

from __future__ import annotations

import pytest

from lib import ha_manager
from lib.secure_store import SecureStoreError, secure_read_json, secure_write_json


@pytest.fixture()
def isolated_ha(tmp_path, monkeypatch):
    monkeypatch.setenv("UPCODE_HARBOR_PASSIVE_PROCESS", "1")
    monkeypatch.setattr(ha_manager, "HA_CONFIG_FILE", str(tmp_path / "ha.json"))
    monkeypatch.setattr(
        ha_manager,
        "HA_HEARTBEATS_FILE",
        str(tmp_path / "ha_heartbeats.json"),
    )
    monkeypatch.setattr(ha_manager, "HA_LOCK_FILE", str(tmp_path / "ha.lock"))
    return tmp_path


def test_passive_tls_process_never_starts_ha_loop(isolated_ha):
    secure_write_json(
        ha_manager.HA_CONFIG_FILE,
        {**ha_manager.DEFAULT_CONFIG, "enabled": True},
    )
    manager = ha_manager.HAManager()
    assert manager._passive is True
    assert manager._running is False
    assert manager._heartbeat_thread is None


def test_separate_managers_merge_heartbeat_updates_under_file_lock(isolated_ha):
    first = ha_manager.HAManager()
    second = ha_manager.HAManager()
    first.record_heartbeat("node-a", "10.0.0.1", 9501, "master")
    second.record_heartbeat("node-b", "10.0.0.2", 9501, "child")

    persisted = secure_read_json(ha_manager.HA_HEARTBEATS_FILE)
    assert set(persisted) == {"node-a", "node-b"}


def test_corrupt_ha_state_fails_closed(isolated_ha):
    with open(ha_manager.HA_CONFIG_FILE, "w", encoding="utf-8") as file:
        file.write("not-json")
    with pytest.raises(SecureStoreError):
        ha_manager.HAManager()
