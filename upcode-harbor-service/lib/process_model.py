"""Runtime enforcement for the supported single web-process model."""

from __future__ import annotations

import fcntl
import os
from pathlib import Path

from lib.secure_store import CONFIG_FILE_MODE, CONFIG_ROOT, ensure_config_directory


WEB_PROCESS_LOCK = Path(
    os.getenv("UPCODE_HARBOR_WEB_PROCESS_LOCK", str(CONFIG_ROOT / "web-process.lock"))
)
_web_lock_descriptor: int | None = None
_web_lock_pid: int | None = None


def acquire_web_process_lock() -> None:
    """Fail startup when another browser-facing API process is active."""

    global _web_lock_descriptor, _web_lock_pid
    current_pid = os.getpid()
    if _web_lock_descriptor is not None and _web_lock_pid == current_pid:
        return
    if _web_lock_descriptor is not None:
        # A pre-fork child must not treat the parent's Python global as its own
        # acquisition. Closing the inherited descriptor leaves the parent's
        # independently held reference intact.
        os.close(_web_lock_descriptor)
        _web_lock_descriptor = None
        _web_lock_pid = None

    ensure_config_directory(WEB_PROCESS_LOCK.parent)
    descriptor = os.open(
        WEB_PROCESS_LOCK,
        os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW,
        CONFIG_FILE_MODE,
    )
    os.fchmod(descriptor, CONFIG_FILE_MODE)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        os.close(descriptor)
        raise RuntimeError(
            "Upcode Harbor supports exactly one browser-facing API worker"
        ) from error
    _web_lock_descriptor = descriptor
    _web_lock_pid = current_pid


def release_web_process_lock() -> None:
    global _web_lock_descriptor, _web_lock_pid
    if _web_lock_descriptor is None:
        return
    try:
        fcntl.flock(_web_lock_descriptor, fcntl.LOCK_UN)
    finally:
        os.close(_web_lock_descriptor)
        _web_lock_descriptor = None
        _web_lock_pid = None


def web_process_lock_held() -> bool:
    """Return whether this process owns the browser-facing singleton lock."""

    return _web_lock_descriptor is not None and _web_lock_pid == os.getpid()
