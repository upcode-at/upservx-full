"""Real cross-process synchronization checks for shared JSON state."""

from __future__ import annotations

import multiprocessing

from lib.file_lock import InterProcessFileLock
from lib.secure_store import secure_read_json, secure_write_json


def _increment_store(path: str, iterations: int) -> None:
    lock = InterProcessFileLock(f"{path}.lock")
    for _ in range(iterations):
        with lock:
            value = secure_read_json(path, missing={"count": 0})
            value["count"] += 1
            secure_write_json(path, value)


def test_file_lock_prevents_lost_cross_process_json_updates(tmp_path):
    path = tmp_path / "counter.json"
    context = multiprocessing.get_context("fork")
    processes = [
        context.Process(target=_increment_store, args=(str(path), 20))
        for _ in range(4)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=20)
        assert process.exitcode == 0

    assert secure_read_json(path) == {"count": 80}
