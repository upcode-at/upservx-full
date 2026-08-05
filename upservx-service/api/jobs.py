"""Administrative API for persistent long-running jobs."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from lib.jobs import (
    InvalidJobStateError,
    JobNotFoundError,
    get_job,
    list_jobs,
    request_cancellation,
    retry_job,
)


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
def get_jobs(
    status: list[str] | None = Query(default=None),
    kind: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
):
    return {"jobs": list_jobs(statuses=status, kind=kind, limit=limit)}


@router.get("/{job_id}")
def get_job_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/cancel")
def cancel_job(job_id: str):
    try:
        return request_cancellation(job_id)
    except JobNotFoundError as error:
        raise HTTPException(status_code=404, detail="Job not found") from error
    except InvalidJobStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/{job_id}/retry")
def retry_failed_job(job_id: str):
    try:
        return retry_job(job_id)
    except JobNotFoundError as error:
        raise HTTPException(status_code=404, detail="Job not found") from error
    except InvalidJobStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
