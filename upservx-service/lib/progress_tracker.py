"""Simple file-backed progress tracker for long-running operations."""

from __future__ import annotations

import fcntl
import json
import os
from datetime import datetime
from typing import Any, Dict, Optional
from lib.secure_store import ensure_config_directory

PROGRESS_FILE = "/etc/upservx/progress.json"
VALID_SCOPES = {"backup_jobs", "replications"}


def _ensure_parent_dir() -> None:
    ensure_config_directory(os.path.dirname(PROGRESS_FILE))


def _read_data_locked(fp) -> Dict[str, Any]:
    fp.seek(0)
    raw = fp.read()
    if not raw.strip():
        return {"backup_jobs": {}, "replications": {}}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {}

    if not isinstance(data, dict):
        data = {}

    data.setdefault("backup_jobs", {})
    data.setdefault("replications", {})
    return data


def _write_data_locked(fp, data: Dict[str, Any]) -> None:
    fp.seek(0)
    fp.truncate(0)
    json.dump(data, fp, indent=2)
    fp.flush()
    os.fsync(fp.fileno())


def _sanitize_progress(progress: float) -> int:
    return max(0, min(100, int(progress)))


def set_progress(
    scope: str,
    key: str,
    *,
    status: str,
    progress: float,
    message: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Set operation progress for one scoped key."""
    if scope not in VALID_SCOPES:
        raise ValueError(f"Unsupported scope: {scope}")

    _ensure_parent_dir()
    entry_key = str(key)
    now = datetime.now().isoformat()
    safe_progress = _sanitize_progress(progress)

    descriptor = os.open(PROGRESS_FILE, os.O_RDWR | os.O_CREAT, 0o600)
    os.chmod(PROGRESS_FILE, 0o600)
    with os.fdopen(descriptor, "r+", encoding="utf-8") as fp:
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX)
        try:
            data = _read_data_locked(fp)
            existing = data[scope].get(entry_key, {})

            started_at = existing.get("started_at")
            if not started_at and status == "running":
                started_at = now

            payload: Dict[str, Any] = {
                "status": status,
                "progress": safe_progress,
                "message": message,
                "updated_at": now,
                "started_at": started_at,
                "completed_at": now if status in {"completed", "failed"} else None,
            }

            if extra:
                payload.update(extra)

            data[scope][entry_key] = payload
            _write_data_locked(fp, data)
            return payload
        finally:
            fcntl.flock(fp.fileno(), fcntl.LOCK_UN)


def get_progress(scope: str, key: str) -> Optional[Dict[str, Any]]:
    """Get operation progress for one scoped key."""
    if scope not in VALID_SCOPES:
        raise ValueError(f"Unsupported scope: {scope}")

    if not os.path.exists(PROGRESS_FILE):
        return None

    os.chmod(PROGRESS_FILE, 0o600)
    with open(PROGRESS_FILE, "r", encoding="utf-8") as fp:
        fcntl.flock(fp.fileno(), fcntl.LOCK_SH)
        try:
            data = _read_data_locked(fp)
            return data.get(scope, {}).get(str(key))
        finally:
            fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
