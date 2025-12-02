"""
API routes for system metrics and overview.
"""

from fastapi import APIRouter
from system_utils import collect_metrics

router = APIRouter()


@router.get("/metrics")
def get_metrics():
    """Get system metrics including CPU, memory, disk, network, and GPU."""
    return collect_metrics()


@router.get("/")
def read_root():
    """Health check endpoint."""
    return {"detail": "ok"}