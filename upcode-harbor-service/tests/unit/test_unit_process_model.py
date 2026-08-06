"""The browser-facing API must fail closed when configured with many workers."""

from __future__ import annotations

import os
import stat

from lib import process_model


def test_second_web_process_cannot_acquire_runtime_lock(tmp_path, monkeypatch):
    process_model.release_web_process_lock()
    lock_path = tmp_path / "web-process.lock"
    monkeypatch.setattr(process_model, "WEB_PROCESS_LOCK", lock_path)
    process_model.acquire_web_process_lock()
    try:
        child_pid = os.fork()
        if child_pid == 0:
            try:
                process_model.acquire_web_process_lock()
            except RuntimeError:
                os._exit(0)
            os._exit(1)
        _pid, status = os.waitpid(child_pid, 0)
        assert os.waitstatus_to_exitcode(status) == 0
        assert stat.S_IMODE(lock_path.stat().st_mode) == 0o600
    finally:
        process_model.release_web_process_lock()
