"""Cron schedules must enqueue through the installed service environment."""

from __future__ import annotations

import sys

import pytest

from lib.crontab_manager import CrontabManager


def test_backup_and_replication_cron_use_service_user_venv_and_queue_scripts(
    monkeypatch,
):
    monkeypatch.setenv("UPCODE_HARBOR_SERVICE_USER", "upcode-harbor-service")
    manager = CrontabManager()

    backup = manager.get_backup_job_cron_entry(7, "0 2 * * *", "nightly")
    replication = manager.get_replication_job_cron_entry(
        "rule-id",
        "30 2 * * *",
        "replica",
    )

    assert f" upcode-harbor-service {sys.executable} " in backup
    assert "/handlers/execute_backup.py 7" in backup
    assert f" upcode-harbor-service {sys.executable} " in replication
    assert "/handlers/execute_replication.py rule-id" in replication


def test_schedule_replacement_and_pause_remove_existing_entry(monkeypatch):
    manager = CrontabManager()
    lines = []

    monkeypatch.setattr(manager, "read_crontab", lambda: list(lines))

    def write_crontab(updated):
        lines[:] = updated
        return True

    monkeypatch.setattr(manager, "write_crontab", write_crontab)
    assert manager.add_backup_job(7, "0 2 * * *", "nightly")
    assert manager.add_backup_job(7, "30 3 * * *", "nightly")
    assert sum("UPCODE_HARBOR_BACKUP_JOB_ID_7" in line for line in lines) == 1
    assert any(line.startswith("30 3 ") for line in lines)
    assert manager.remove_backup_job(7)
    assert not any("UPCODE_HARBOR_BACKUP_JOB_ID_7" in line for line in lines)


@pytest.mark.parametrize("schedule", ("60 2 * * *", "0 24 * * *", "*/0 * * * *"))
def test_invalid_cron_ranges_are_rejected(schedule):
    with pytest.raises(ValueError):
        CrontabManager._validate_schedule(schedule)
