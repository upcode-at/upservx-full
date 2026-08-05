"""Cross-process locks for shared UpservX state files."""

from __future__ import annotations

import fcntl
import os
import threading
from pathlib import Path
from types import TracebackType
from typing import Optional, Type

from lib.secure_store import CONFIG_FILE_MODE, ensure_config_directory


class InterProcessFileLock:
    """A thread-safe, re-entrant advisory lock backed by ``flock``.

    ``threading.Lock`` only protects one interpreter.  UpservX state is also
    touched by the API, scheduler scripts, and the persistent job worker, so
    every read/modify/write section must use a kernel-visible lock.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._thread_lock = threading.RLock()
        self._local = threading.local()

    def acquire(self) -> "InterProcessFileLock":
        self._thread_lock.acquire()
        depth = getattr(self._local, "depth", 0)
        if depth:
            self._local.depth = depth + 1
            return self

        try:
            ensure_config_directory(self.path.parent)
            descriptor = os.open(
                self.path,
                os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW,
                CONFIG_FILE_MODE,
            )
            os.fchmod(descriptor, CONFIG_FILE_MODE)
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            self._local.descriptor = descriptor
            self._local.depth = 1
            return self
        except Exception:
            self._thread_lock.release()
            raise

    def release(self) -> None:
        depth = getattr(self._local, "depth", 0)
        if depth <= 0:
            raise RuntimeError("Cannot release an unlocked file lock")
        if depth > 1:
            self._local.depth = depth - 1
            self._thread_lock.release()
            return

        descriptor = self._local.descriptor
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)
            del self._local.descriptor
            self._local.depth = 0
            self._thread_lock.release()

    def __enter__(self) -> "InterProcessFileLock":
        return self.acquire()

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        self.release()
