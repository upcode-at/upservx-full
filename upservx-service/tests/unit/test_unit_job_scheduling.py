"""Cron schedules must enqueue through the installed service environment."""

from __future__ import annotations

import sys

from lib.crontab_manager import CrontabManager


def test_backup_and_replication_cron_use_service_user_venv_and_queue_scripts(
    monkeypatch,
):
    monkeypatch.setenv("UPSERVX_SERVICE_USER", "upservx-service")
    manager = CrontabManager()

    backup = manager.get_backup_job_cron_entry(7, "0 2 * * *", "nightly")
    replication = manager.get_replication_job_cron_entry(
        "rule-id",
        "30 2 * * *",
        "replica",
    )

    assert f" upservx-service {sys.executable} " in backup
    assert "/handlers/execute_backup.py 7" in backup
    assert f" upservx-service {sys.executable} " in replication
    assert "/handlers/execute_replication.py rule-id" in replication
