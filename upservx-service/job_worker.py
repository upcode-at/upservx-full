#!/usr/bin/env python3
"""Dedicated supervisor for persistent Upcode Harbor jobs."""

from __future__ import annotations

import fcntl
import logging
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from lib.jobs import (
    CANCEL_REQUESTED,
    RUNNING,
    claim_next_job,
    fail_job,
    get_job,
    initialize_job_store,
    mark_job_cancelled,
    recover_stale_jobs,
    touch_job,
)
from lib.secure_store import (
    CONFIG_FILE_MODE,
    CONFIG_ROOT,
    apply_secure_umask,
    ensure_config_directory,
)


logger = logging.getLogger("upservx.job-worker")
POLL_SECONDS = float(os.getenv("UPSERVX_JOB_POLL_SECONDS", "1"))
HEARTBEAT_SECONDS = float(os.getenv("UPSERVX_JOB_HEARTBEAT_SECONDS", "5"))
WORKER_LOCK = Path(os.getenv("UPSERVX_JOB_WORKER_LOCK", str(CONFIG_ROOT / "job-worker.lock")))
RUNNER_PATH = Path(__file__).with_name("job_runner.py")


class JobWorker:
    def __init__(self) -> None:
        self.worker_id = f"{socket.gethostname()}:{os.getpid()}"
        self.stopping = False
        self.process: subprocess.Popen | None = None
        self.active_job_id: str | None = None
        self.release_runner = Path(__file__).resolve()

    def stop(self, *_args: object) -> None:
        self.stopping = True

    @staticmethod
    def _terminate_process(process: subprocess.Popen) -> None:
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=10)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=5)

    def _run_claimed(self, job: dict) -> None:
        job_id = job["id"]
        timeout_seconds = int(job["timeout_seconds"])
        self.active_job_id = job_id
        started = time.monotonic()
        last_heartbeat = 0.0
        self.process = subprocess.Popen(
            [sys.executable, str(RUNNER_PATH), job_id],
            cwd=str(RUNNER_PATH.parent),
            start_new_session=True,
        )
        logger.info("Started %s job %s", job["kind"], job_id)
        try:
            while self.process.poll() is None:
                current = get_job(job_id)
                if current is None:
                    self._terminate_process(self.process)
                    return
                if current["status"] == CANCEL_REQUESTED:
                    self._terminate_process(self.process)
                    current = get_job(job_id)
                    if current and current["status"] in (RUNNING, CANCEL_REQUESTED):
                        mark_job_cancelled(job_id)
                    logger.info("Cancelled job %s", job_id)
                    return
                if self.stopping:
                    self._terminate_process(self.process)
                    current = get_job(job_id)
                    if current and current["status"] in (RUNNING, CANCEL_REQUESTED):
                        fail_job(job_id, "Job worker is shutting down", retry=True)
                    return
                if time.monotonic() - started >= timeout_seconds:
                    self._terminate_process(self.process)
                    current = get_job(job_id)
                    if current and current["status"] in (RUNNING, CANCEL_REQUESTED):
                        fail_job(
                            job_id,
                            f"Job exceeded its {timeout_seconds}-second timeout",
                            retry=True,
                        )
                    logger.error("Timed out job %s", job_id)
                    return
                if time.monotonic() - last_heartbeat >= HEARTBEAT_SECONDS:
                    touch_job(job_id, self.worker_id)
                    last_heartbeat = time.monotonic()
                time.sleep(min(0.5, POLL_SECONDS))

            current = get_job(job_id)
            if current and current["status"] == CANCEL_REQUESTED:
                mark_job_cancelled(job_id)
            elif current and current["status"] == RUNNING:
                fail_job(
                    job_id,
                    f"Job runner exited unexpectedly with code {self.process.returncode}",
                    retry=True,
                )
        finally:
            self.process = None
            self.active_job_id = None

    def run_forever(self) -> None:
        recovered = recover_stale_jobs(stale_after_seconds=0)
        if recovered:
            logger.warning("Recovered %d interrupted job(s)", len(recovered))
        while not self.stopping:
            job = claim_next_job(self.worker_id)
            if job is None:
                time.sleep(POLL_SECONDS)
                continue
            self._run_claimed(job)
            installed_runner = Path(
                "/opt/upservx/current/upservx-service/job_worker.py"
            )
            if installed_runner.exists() and installed_runner.resolve() != self.release_runner:
                logger.info("A new release is active; restarting the job worker")
                return


def _acquire_singleton_lock() -> int:
    ensure_config_directory(WORKER_LOCK.parent)
    descriptor = os.open(
        WORKER_LOCK,
        os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW,
        CONFIG_FILE_MODE,
    )
    os.fchmod(descriptor, CONFIG_FILE_MODE)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(descriptor)
        raise RuntimeError("Another Upcode Harbor job worker is already running")
    return descriptor


def main() -> int:
    apply_secure_umask()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    initialize_job_store()
    lock_descriptor = _acquire_singleton_lock()
    worker = JobWorker()
    signal.signal(signal.SIGTERM, worker.stop)
    signal.signal(signal.SIGINT, worker.stop)
    try:
        worker.run_forever()
        return 0
    finally:
        fcntl.flock(lock_descriptor, fcntl.LOCK_UN)
        os.close(lock_descriptor)


if __name__ == "__main__":
    raise SystemExit(main())
