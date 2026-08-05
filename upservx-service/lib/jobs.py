"""Transactional persistent jobs shared by the API and job worker."""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from lib.secure_store import (
    CONFIG_FILE_MODE,
    CONFIG_ROOT,
    SecureStoreError,
    ensure_config_directory,
)


JOB_DB_PATH = Path(os.getenv("UPSERVX_JOB_DB", str(CONFIG_ROOT / "jobs.db")))

QUEUED = "queued"
RUNNING = "running"
RETRY_WAIT = "retry_wait"
CANCEL_REQUESTED = "cancel_requested"
COMPLETED = "completed"
FAILED = "failed"
CANCELLED = "cancelled"

ACTIVE_STATUSES = (QUEUED, RUNNING, RETRY_WAIT, CANCEL_REQUESTED)
TERMINAL_STATUSES = (COMPLETED, FAILED, CANCELLED)

JOB_DEFAULTS: dict[str, tuple[int, int]] = {
    # kind: (timeout seconds, maximum attempts)
    "backup": (24 * 60 * 60, 3),
    "replication": (24 * 60 * 60, 3),
    "vm_export": (4 * 60 * 60, 2),
    "cluster_export": (4 * 60 * 60, 2),
    "cve_scan": (60 * 60, 2),
    "container_cve_scan": (2 * 60 * 60, 2),
    "package_scan": (30 * 60, 2),
    "package_upgrade": (2 * 60 * 60, 2),
    "system_update": (2 * 60 * 60, 2),
}


class JobError(RuntimeError):
    """Base class for job-store failures."""


class JobNotFoundError(JobError):
    """Raised when a job identifier does not exist."""


class InvalidJobStateError(JobError):
    """Raised when a lifecycle operation is invalid for the current state."""


class JobCancelledError(JobError):
    """Raised inside a job when cancellation has been requested."""


def _now() -> float:
    return time.time()


def _connect() -> sqlite3.Connection:
    ensure_config_directory(JOB_DB_PATH.parent)
    descriptor: int | None = None
    try:
        descriptor = os.open(
            JOB_DB_PATH,
            os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW,
            CONFIG_FILE_MODE,
        )
        os.fchmod(descriptor, CONFIG_FILE_MODE)
    except OSError as error:
        raise SecureStoreError(f"Unable to secure job database {JOB_DB_PATH}") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
    connection = sqlite3.connect(
        str(JOB_DB_PATH),
        timeout=30,
        isolation_level=None,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = FULL")
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        os.chmod(JOB_DB_PATH, CONFIG_FILE_MODE)
        for suffix in ("-wal", "-shm"):
            auxiliary = Path(f"{JOB_DB_PATH}{suffix}")
            if auxiliary.exists():
                os.chmod(auxiliary, CONFIG_FILE_MODE)
    except OSError as error:
        connection.close()
        raise SecureStoreError(f"Unable to secure job database {JOB_DB_PATH}") from error
    return connection


@contextmanager
def _connection():
    connection = _connect()
    try:
        yield connection
    finally:
        connection.close()


def initialize_job_store() -> None:
    """Create the durable queue schema; safe to call from every process."""

    with _connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,
                message TEXT,
                result TEXT,
                error TEXT,
                checkpoint TEXT,
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL,
                timeout_seconds INTEGER NOT NULL,
                available_at REAL NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                started_at REAL,
                finished_at REAL,
                heartbeat_at REAL,
                worker_id TEXT,
                idempotency_key TEXT,
                resource_type TEXT,
                resource_id TEXT
            );
            CREATE INDEX IF NOT EXISTS jobs_claim_idx
                ON jobs(status, available_at, created_at);
            CREATE INDEX IF NOT EXISTS jobs_resource_idx
                ON jobs(resource_type, resource_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS jobs_idempotency_idx
                ON jobs(kind, idempotency_key, created_at DESC);
            """
        )


def _encode(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _decode(value: Optional[str], default: Any) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError) as error:
        raise JobError("Persistent job data is corrupt") from error


def _iso(timestamp: Optional[float]) -> Optional[str]:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def _record(row: sqlite3.Row | None) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    record = dict(row)
    record["payload"] = _decode(record.get("payload"), {})
    record["result"] = _decode(record.get("result"), None)
    record["checkpoint"] = _decode(record.get("checkpoint"), None)
    for key in (
        "available_at",
        "created_at",
        "updated_at",
        "started_at",
        "finished_at",
        "heartbeat_at",
    ):
        record[key] = _iso(record.get(key))
    return record


def enqueue_job(
    kind: str,
    payload: Mapping[str, Any] | None = None,
    *,
    max_attempts: int | None = None,
    timeout_seconds: int | None = None,
    idempotency_key: str | None = None,
    resource_type: str | None = None,
    resource_id: str | int | None = None,
) -> dict[str, Any]:
    """Atomically enqueue a supported job, deduplicating active requests."""

    if kind not in JOB_DEFAULTS:
        raise JobError(f"Unsupported job kind: {kind}")
    default_timeout, default_attempts = JOB_DEFAULTS[kind]
    timeout_seconds = default_timeout if timeout_seconds is None else int(timeout_seconds)
    max_attempts = default_attempts if max_attempts is None else int(max_attempts)
    if timeout_seconds < 1 or max_attempts < 1:
        raise JobError("Job timeout and maximum attempts must be positive")
    payload_json = _encode(dict(payload or {}))
    resource_id_text = None if resource_id is None else str(resource_id)
    timestamp = _now()
    job_id = str(uuid.uuid4())

    initialize_job_store()
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        if idempotency_key:
            placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
            row = connection.execute(
                f"""
                SELECT * FROM jobs
                WHERE kind = ? AND idempotency_key = ?
                  AND status IN ({placeholders})
                ORDER BY created_at DESC LIMIT 1
                """,
                (kind, idempotency_key, *ACTIVE_STATUSES),
            ).fetchone()
            if row is not None:
                connection.commit()
                return _record(row)  # type: ignore[return-value]
        connection.execute(
            """
            INSERT INTO jobs (
                id, kind, payload, status, progress, message, attempts,
                max_attempts, timeout_seconds, available_at, created_at,
                updated_at, idempotency_key, resource_type, resource_id
            ) VALUES (?, ?, ?, ?, 0, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                kind,
                payload_json,
                QUEUED,
                "Waiting for a worker",
                max_attempts,
                timeout_seconds,
                timestamp,
                timestamp,
                timestamp,
                idempotency_key,
                resource_type,
                resource_id_text,
            ),
        )
        row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        connection.commit()
        return _record(row)  # type: ignore[return-value]
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_job(job_id: str) -> Optional[dict[str, Any]]:
    initialize_job_store()
    with _connection() as connection:
        return _record(connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone())


def require_job(job_id: str) -> dict[str, Any]:
    job = get_job(job_id)
    if job is None:
        raise JobNotFoundError(f"Job {job_id} was not found")
    return job


def list_jobs(
    *,
    statuses: Iterable[str] | None = None,
    kind: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    initialize_job_store()
    limit = max(1, min(int(limit), 500))
    clauses: list[str] = []
    parameters: list[Any] = []
    status_values = tuple(statuses or ())
    if status_values:
        clauses.append(f"status IN ({','.join('?' for _ in status_values)})")
        parameters.extend(status_values)
    if kind:
        clauses.append("kind = ?")
        parameters.append(kind)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    parameters.append(limit)
    with _connection() as connection:
        rows = connection.execute(
            f"SELECT * FROM jobs {where} ORDER BY created_at DESC LIMIT ?",
            parameters,
        ).fetchall()
    return [_record(row) for row in rows]  # type: ignore[misc]


def find_latest_job(resource_type: str, resource_id: str | int) -> Optional[dict[str, Any]]:
    initialize_job_store()
    with _connection() as connection:
        row = connection.execute(
            """
            SELECT * FROM jobs WHERE resource_type = ? AND resource_id = ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (resource_type, str(resource_id)),
        ).fetchone()
    return _record(row)


def claim_next_job(worker_id: str) -> Optional[dict[str, Any]]:
    """Claim exactly one available job using a write transaction."""

    initialize_job_store()
    timestamp = _now()
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            """
            SELECT * FROM jobs
            WHERE status IN (?, ?) AND available_at <= ?
            ORDER BY available_at ASC, created_at ASC
            LIMIT 1
            """,
            (QUEUED, RETRY_WAIT, timestamp),
        ).fetchone()
        if row is None:
            connection.commit()
            return None
        changed = connection.execute(
            """
            UPDATE jobs SET
                status = ?, attempts = attempts + 1, progress = 0,
                message = ?, error = NULL, started_at = ?, finished_at = NULL,
                heartbeat_at = ?, worker_id = ?, updated_at = ?
            WHERE id = ? AND status IN (?, ?)
            """,
            (
                RUNNING,
                "Job started",
                timestamp,
                timestamp,
                worker_id,
                timestamp,
                row["id"],
                QUEUED,
                RETRY_WAIT,
            ),
        ).rowcount
        if changed != 1:
            connection.rollback()
            return None
        claimed = connection.execute("SELECT * FROM jobs WHERE id = ?", (row["id"],)).fetchone()
        connection.commit()
        return _record(claimed)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def touch_job(job_id: str, worker_id: str) -> bool:
    timestamp = _now()
    with _connection() as connection:
        changed = connection.execute(
            """
            UPDATE jobs SET heartbeat_at = ?, updated_at = ?
            WHERE id = ? AND worker_id = ? AND status IN (?, ?)
            """,
            (timestamp, timestamp, job_id, worker_id, RUNNING, CANCEL_REQUESTED),
        ).rowcount
    return changed == 1


def update_job_progress(
    job_id: str,
    progress: int,
    message: str | None = None,
    *,
    checkpoint: Any = None,
    store_checkpoint: bool = False,
) -> dict[str, Any]:
    timestamp = _now()
    progress = max(0, min(100, int(progress)))
    assignments = ["progress = ?", "updated_at = ?", "heartbeat_at = ?"]
    parameters: list[Any] = [progress, timestamp, timestamp]
    if message is not None:
        assignments.append("message = ?")
        parameters.append(str(message)[:2000])
    if store_checkpoint:
        assignments.append("checkpoint = ?")
        parameters.append(_encode(checkpoint))
    parameters.extend((job_id, RUNNING, CANCEL_REQUESTED))
    with _connection() as connection:
        changed = connection.execute(
            f"UPDATE jobs SET {', '.join(assignments)} WHERE id = ? AND status IN (?, ?)",
            parameters,
        ).rowcount
    if changed != 1:
        raise InvalidJobStateError(f"Job {job_id} is not active")
    return require_job(job_id)


def is_cancellation_requested(job_id: str) -> bool:
    with _connection() as connection:
        row = connection.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        raise JobNotFoundError(f"Job {job_id} was not found")
    return row["status"] in (CANCEL_REQUESTED, CANCELLED)


def request_cancellation(job_id: str) -> dict[str, Any]:
    timestamp = _now()
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise JobNotFoundError(f"Job {job_id} was not found")
        status = row["status"]
        if status in (QUEUED, RETRY_WAIT):
            connection.execute(
                """
                UPDATE jobs SET status = ?, message = ?, finished_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (CANCELLED, "Cancelled before execution", timestamp, timestamp, job_id),
            )
        elif status == RUNNING:
            connection.execute(
                "UPDATE jobs SET status = ?, message = ?, updated_at = ? WHERE id = ?",
                (CANCEL_REQUESTED, "Cancellation requested", timestamp, job_id),
            )
        elif status == CANCEL_REQUESTED:
            pass
        else:
            raise InvalidJobStateError(f"Cannot cancel a {status} job")
        updated = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        connection.commit()
        return _record(updated)  # type: ignore[return-value]
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def mark_job_cancelled(job_id: str, message: str = "Job cancelled") -> dict[str, Any]:
    timestamp = _now()
    with _connection() as connection:
        changed = connection.execute(
            """
            UPDATE jobs SET status = ?, message = ?, finished_at = ?,
                heartbeat_at = ?, updated_at = ?, worker_id = NULL
            WHERE id = ? AND status IN (?, ?)
            """,
            (
                CANCELLED,
                message[:2000],
                timestamp,
                timestamp,
                timestamp,
                job_id,
                RUNNING,
                CANCEL_REQUESTED,
            ),
        ).rowcount
    if changed != 1:
        raise InvalidJobStateError(f"Job {job_id} cannot be marked cancelled")
    return require_job(job_id)


def complete_job(job_id: str, result: Any = None) -> dict[str, Any]:
    timestamp = _now()
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise JobNotFoundError(f"Job {job_id} was not found")
        if row["status"] == CANCEL_REQUESTED:
            connection.execute(
                """
                UPDATE jobs SET status = ?, message = ?, finished_at = ?,
                    heartbeat_at = ?, updated_at = ?, worker_id = NULL
                WHERE id = ?
                """,
                (CANCELLED, "Cancelled", timestamp, timestamp, timestamp, job_id),
            )
        elif row["status"] == RUNNING:
            connection.execute(
                """
                UPDATE jobs SET status = ?, progress = 100, message = ?, result = ?,
                    error = NULL, finished_at = ?, heartbeat_at = ?, updated_at = ?,
                    worker_id = NULL
                WHERE id = ?
                """,
                (
                    COMPLETED,
                    "Completed",
                    _encode(result),
                    timestamp,
                    timestamp,
                    timestamp,
                    job_id,
                ),
            )
        else:
            raise InvalidJobStateError(f"Cannot complete a {row['status']} job")
        updated = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        connection.commit()
        return _record(updated)  # type: ignore[return-value]
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def fail_job(job_id: str, error: str, *, retry: bool = True) -> dict[str, Any]:
    """Record a failure and schedule retry when attempts remain."""

    timestamp = _now()
    error = str(error)[:8000]
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise JobNotFoundError(f"Job {job_id} was not found")
        if row["status"] == CANCEL_REQUESTED:
            next_status = CANCELLED
            available_at = timestamp
            message = "Cancelled"
        elif row["status"] != RUNNING:
            raise InvalidJobStateError(f"Cannot fail a {row['status']} job")
        elif retry and row["attempts"] < row["max_attempts"]:
            next_status = RETRY_WAIT
            delay = min(300, 2 ** max(0, int(row["attempts"])))
            available_at = timestamp + delay
            message = f"Attempt {row['attempts']} failed; retry scheduled"
        else:
            next_status = FAILED
            available_at = timestamp
            message = "Job failed"
        finished_at = timestamp if next_status in TERMINAL_STATUSES else None
        connection.execute(
            """
            UPDATE jobs SET status = ?, message = ?, error = ?, available_at = ?,
                finished_at = ?, heartbeat_at = ?, updated_at = ?, worker_id = NULL
            WHERE id = ?
            """,
            (
                next_status,
                message,
                error,
                available_at,
                finished_at,
                timestamp,
                timestamp,
                job_id,
            ),
        )
        updated = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        connection.commit()
        return _record(updated)  # type: ignore[return-value]
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def retry_job(job_id: str) -> dict[str, Any]:
    timestamp = _now()
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise JobNotFoundError(f"Job {job_id} was not found")
        if row["status"] not in TERMINAL_STATUSES:
            raise InvalidJobStateError(f"Cannot retry a {row['status']} job")
        connection.execute(
            """
            UPDATE jobs SET status = ?, progress = 0, message = ?, error = NULL,
                result = NULL, attempts = 0, available_at = ?, updated_at = ?,
                started_at = NULL, finished_at = NULL, heartbeat_at = NULL,
                worker_id = NULL
            WHERE id = ?
            """,
            (QUEUED, "Waiting for a worker", timestamp, timestamp, job_id),
        )
        updated = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        connection.commit()
        return _record(updated)  # type: ignore[return-value]
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def recover_stale_jobs(stale_after_seconds: int = 60) -> list[dict[str, Any]]:
    """Recover jobs abandoned by a dead worker without losing checkpoints."""

    initialize_job_store()
    timestamp = _now()
    cutoff = timestamp - max(0, int(stale_after_seconds))
    recovered_ids: list[str] = []
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        rows = connection.execute(
            """
            SELECT * FROM jobs
            WHERE status IN (?, ?) AND (heartbeat_at IS NULL OR heartbeat_at < ?)
            """,
            (RUNNING, CANCEL_REQUESTED, cutoff),
        ).fetchall()
        for row in rows:
            if row["status"] == CANCEL_REQUESTED:
                status = CANCELLED
                message = "Cancelled after worker restart"
                finished_at = timestamp
            elif row["attempts"] < row["max_attempts"]:
                status = RETRY_WAIT
                message = "Recovered after worker restart; retry scheduled"
                finished_at = None
            else:
                status = FAILED
                message = "Worker stopped and no retries remain"
                finished_at = timestamp
            connection.execute(
                """
                UPDATE jobs SET status = ?, message = ?, error = ?, available_at = ?,
                    finished_at = ?, worker_id = NULL, updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    message,
                    "The worker stopped before the job finished",
                    timestamp,
                    finished_at,
                    timestamp,
                    row["id"],
                ),
            )
            recovered_ids.append(row["id"])
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return [require_job(job_id) for job_id in recovered_ids]


class JobContext:
    """Progress, checkpoint, and cooperative-cancellation interface for tasks."""

    def __init__(self, job_id: str):
        self.job_id = job_id

    @property
    def checkpoint(self) -> Any:
        return require_job(self.job_id).get("checkpoint")

    def check_cancelled(self) -> None:
        if is_cancellation_requested(self.job_id):
            raise JobCancelledError("Cancellation requested")

    def progress(
        self,
        percent: int,
        message: str | None = None,
        *,
        checkpoint: Any = None,
        save_checkpoint: bool = False,
    ) -> None:
        self.check_cancelled()
        update_job_progress(
            self.job_id,
            percent,
            message,
            checkpoint=checkpoint,
            store_checkpoint=save_checkpoint,
        )
