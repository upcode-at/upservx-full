#!/usr/bin/env python3
"""Execute one already-claimed persistent job in an isolated process."""

from __future__ import annotations

import logging
import sys

from handlers.job_tasks import run_task
from lib.jobs import (
    JobCancelledError,
    JobContext,
    complete_job,
    fail_job,
    mark_job_cancelled,
    require_job,
)
from lib.secure_store import apply_secure_umask


logger = logging.getLogger("upcode-harbor.job-runner")


def run(job_id: str) -> int:
    job = require_job(job_id)
    if job["status"] not in ("running", "cancel_requested"):
        logger.error("Refusing to run job %s in state %s", job_id, job["status"])
        return 2

    context = JobContext(job_id)
    try:
        context.check_cancelled()
        result = run_task(job["kind"], job["payload"], context)
        complete_job(job_id, result)
        return 0
    except JobCancelledError:
        mark_job_cancelled(job_id)
        return 0
    except Exception as error:
        logger.exception("Job %s failed", job_id)
        fail_job(job_id, str(error), retry=True)
        return 1


def main() -> int:
    apply_secure_umask()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    if len(sys.argv) != 2:
        logger.error("Usage: job_runner.py <job-id>")
        return 2
    return run(sys.argv[1])


if __name__ == "__main__":
    raise SystemExit(main())
