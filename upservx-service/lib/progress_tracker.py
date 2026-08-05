"""Simple file-backed progress tracker for long-running operations."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, Optional
from lib.file_lock import InterProcessFileLock
from lib.secure_store import ensure_config_directory, secure_read_json, secure_write_json

PROGRESS_FILE = "/etc/upservx/progress.json"
VALID_SCOPES = {"backup_jobs", "replications"}


def _ensure_parent_dir() -> None:
    ensure_config_directory(os.path.dirname(PROGRESS_FILE))


def _read_data() -> Dict[str, Any]:
    data = secure_read_json(PROGRESS_FILE, missing={})
    if not isinstance(data, dict):
        raise ValueError("Invalid progress store")
    data.setdefault("backup_jobs", {})
    data.setdefault("replications", {})
    return data


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

    with InterProcessFileLock(f"{PROGRESS_FILE}.lock"):
        data = _read_data()
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
        secure_write_json(PROGRESS_FILE, data)
        return payload


def get_progress(scope: str, key: str) -> Optional[Dict[str, Any]]:
    """Get operation progress for one scoped key."""
    if scope not in VALID_SCOPES:
        raise ValueError(f"Unsupported scope: {scope}")

    if not os.path.exists(PROGRESS_FILE):
        return None

    with InterProcessFileLock(f"{PROGRESS_FILE}.lock"):
        data = _read_data()
        return data.get(scope, {}).get(str(key))
