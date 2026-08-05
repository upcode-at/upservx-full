"""Single durable entry point for manual, UI, CLI, and cron backup runs."""

from __future__ import annotations

from lib.backup_db import backup_db
from lib.jobs import enqueue_job


def queue_backup_job(job_id: int) -> dict:
    """Validate and enqueue one backup job through the persistent worker."""
    job = backup_db.get_backup_job(int(job_id))
    if not job:
        raise LookupError("Backup job not found")
    return enqueue_job(
        "backup",
        {"backup_job_id": int(job_id)},
        idempotency_key=f"backup:{int(job_id)}",
        resource_type="backup_job",
        resource_id=int(job_id),
    )
