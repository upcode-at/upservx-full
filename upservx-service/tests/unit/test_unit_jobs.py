"""Tests for the transactional persistent job lifecycle."""

from __future__ import annotations

import stat
from concurrent.futures import ThreadPoolExecutor

import pytest

from lib import jobs


@pytest.fixture()
def job_store(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "JOB_DB_PATH", tmp_path / "jobs.db")
    jobs.initialize_job_store()
    return tmp_path / "jobs.db"


def test_job_lifecycle_persists_payload_progress_checkpoint_and_result(job_store):
    queued = jobs.enqueue_job(
        "vm_export",
        {"name": "demo", "format": "ova"},
        resource_type="vm_export",
        resource_id="demo",
    )
    assert queued["status"] == jobs.QUEUED

    claimed = jobs.claim_next_job("worker-a")
    assert claimed is not None
    assert claimed["id"] == queued["id"]
    assert claimed["attempts"] == 1
    jobs.update_job_progress(
        claimed["id"],
        45,
        "Exporting disks",
        checkpoint={"disk": 2},
        store_checkpoint=True,
    )
    completed = jobs.complete_job(claimed["id"], {"filename": "demo.ova"})

    assert completed["status"] == jobs.COMPLETED
    assert completed["progress"] == 100
    assert completed["checkpoint"] == {"disk": 2}
    assert completed["result"] == {"filename": "demo.ova"}
    assert jobs.find_latest_job("vm_export", "demo")["id"] == queued["id"]
    assert stat.S_IMODE(job_store.stat().st_mode) == 0o600


def test_claim_is_transactional_across_competing_workers(job_store):
    queued = jobs.enqueue_job("cve_scan", {"limit": 100})

    with ThreadPoolExecutor(max_workers=2) as executor:
        claims = list(executor.map(jobs.claim_next_job, ("worker-a", "worker-b")))

    claimed = [job for job in claims if job is not None]
    assert len(claimed) == 1
    assert claimed[0]["id"] == queued["id"]


def test_active_idempotency_key_deduplicates_but_terminal_job_does_not(job_store):
    first = jobs.enqueue_job(
        "backup",
        {"backup_job_id": 7},
        idempotency_key="backup:7",
    )
    duplicate = jobs.enqueue_job(
        "backup",
        {"backup_job_id": 7},
        idempotency_key="backup:7",
    )
    assert duplicate["id"] == first["id"]

    jobs.claim_next_job("worker-a")
    jobs.complete_job(first["id"], {"ok": True})
    next_run = jobs.enqueue_job(
        "backup",
        {"backup_job_id": 7},
        idempotency_key="backup:7",
    )
    assert next_run["id"] != first["id"]


def test_failure_retries_then_becomes_terminal(job_store, monkeypatch):
    current_time = [100.0]
    monkeypatch.setattr(jobs, "_now", lambda: current_time[0])
    queued = jobs.enqueue_job("package_upgrade", {}, max_attempts=2)

    first_attempt = jobs.claim_next_job("worker-a")
    failed_once = jobs.fail_job(first_attempt["id"], "temporary failure")
    assert failed_once["status"] == jobs.RETRY_WAIT
    assert jobs.claim_next_job("worker-a") is None

    current_time[0] = 103.0
    second_attempt = jobs.claim_next_job("worker-a")
    assert second_attempt["attempts"] == 2
    terminal = jobs.fail_job(second_attempt["id"], "permanent failure")
    assert terminal["status"] == jobs.FAILED
    assert terminal["finished_at"] is not None
    assert jobs.require_job(queued["id"])["error"] == "permanent failure"


def test_cancellation_is_immediate_when_queued_and_cooperative_when_running(job_store):
    queued = jobs.enqueue_job("cve_scan", {})
    cancelled = jobs.request_cancellation(queued["id"])
    assert cancelled["status"] == jobs.CANCELLED

    running = jobs.enqueue_job("container_cve_scan", {})
    jobs.claim_next_job("worker-a")
    requested = jobs.request_cancellation(running["id"])
    assert requested["status"] == jobs.CANCEL_REQUESTED
    assert jobs.is_cancellation_requested(running["id"]) is True
    stopped = jobs.mark_job_cancelled(running["id"])
    assert stopped["status"] == jobs.CANCELLED


def test_restart_recovery_retains_checkpoint_and_never_leaves_running(job_store, monkeypatch):
    current_time = [100.0]
    monkeypatch.setattr(jobs, "_now", lambda: current_time[0])
    queued = jobs.enqueue_job("replication", {"replication_id": "rule-1"})
    jobs.claim_next_job("old-worker")
    jobs.update_job_progress(
        queued["id"],
        65,
        "Archive uploaded",
        checkpoint={"stage": "uploaded", "path": "/tmp/archive"},
        store_checkpoint=True,
    )

    current_time[0] = 200.0
    recovered = jobs.recover_stale_jobs(stale_after_seconds=60)
    assert len(recovered) == 1
    assert recovered[0]["status"] == jobs.RETRY_WAIT
    assert recovered[0]["checkpoint"] == {
        "stage": "uploaded",
        "path": "/tmp/archive",
    }
    assert not jobs.list_jobs(statuses=[jobs.RUNNING, jobs.CANCEL_REQUESTED])


def test_manual_retry_resets_a_terminal_job(job_store):
    queued = jobs.enqueue_job("cve_scan", {}, max_attempts=1)
    jobs.claim_next_job("worker-a")
    jobs.fail_job(queued["id"], "failed")
    retried = jobs.retry_job(queued["id"])
    assert retried["status"] == jobs.QUEUED
    assert retried["attempts"] == 0
    assert retried["error"] is None


def test_unsupported_job_kind_is_rejected(job_store):
    with pytest.raises(jobs.JobError, match="Unsupported job kind"):
        jobs.enqueue_job("arbitrary-python", {})


def test_worker_enforces_hard_timeout_and_retries(job_store, monkeypatch):
    import job_worker

    class FakeProcess:
        pid = 12345
        returncode = None

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = -15

    worker = job_worker.JobWorker()
    queued = jobs.enqueue_job(
        "cve_scan",
        {},
        timeout_seconds=1,
        max_attempts=2,
    )
    claimed = jobs.claim_next_job(worker.worker_id)
    fake_process = FakeProcess()
    monkeypatch.setattr(job_worker.subprocess, "Popen", lambda *_args, **_kwargs: fake_process)
    monotonic_values = iter((0.0, 2.0))
    monkeypatch.setattr(job_worker.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(worker, "_terminate_process", lambda process: process.terminate())

    worker._run_claimed(claimed)

    timed_out = jobs.require_job(queued["id"])
    assert fake_process.returncode == -15
    assert timed_out["status"] == jobs.RETRY_WAIT
    assert "timeout" in timed_out["error"]


def test_vm_export_resumes_from_persisted_final_checkpoint(job_store, tmp_path):
    from handlers import job_tasks

    export_path = tmp_path / "demo.ova"
    export_path.write_bytes(b"completed export")
    queued = jobs.enqueue_job("vm_export", {"name": "demo", "format": "ova"})
    jobs.claim_next_job("worker-a")
    jobs.update_job_progress(
        queued["id"],
        95,
        "Finalizing",
        checkpoint={"stage": "finalizing", "path": str(export_path)},
        store_checkpoint=True,
    )

    result = job_tasks._vm_export(
        {"name": "demo", "format": "ova"},
        jobs.JobContext(queued["id"]),
    )

    assert result["resumed"] is True
    assert result["filename"] == "demo.ova"
