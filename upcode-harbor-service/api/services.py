"""Systemd service management routes."""

from fastapi import APIRouter, HTTPException

from lib.logger import log_service
from handlers.services import (
    list_systemd_services, start_service, stop_service,
    enable_service, disable_service,
)

router = APIRouter()


@router.get("/services")
def api_list_services():
    """List systemd services."""
    return {"services": [s.dict() for s in list_systemd_services()]}


@router.post("/services/{name}/start")
def api_start_service(name: str):
    """Start a systemd service."""
    try:
        start_service(name)
        log_service(f"Started service [{name}]")
        return {"detail": "started"}
    except Exception as e:
        log_service(f"Failed to start service [{name}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/services/{name}/stop")
def api_stop_service(name: str):
    """Stop a systemd service."""
    try:
        stop_service(name)
        log_service(f"Stopped service [{name}]")
        return {"detail": "stopped"}
    except Exception as e:
        log_service(f"Failed to stop service [{name}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/services/{name}/enable")
def api_enable_service(name: str):
    """Enable a systemd service."""
    try:
        enable_service(name)
        log_service(f"Enabled service [{name}]")
        return {"detail": "enabled"}
    except Exception as e:
        log_service(f"Failed to enable service [{name}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/services/{name}/disable")
def api_disable_service(name: str):
    """Disable a systemd service."""
    try:
        disable_service(name)
        log_service(f"Disabled service [{name}]")
        return {"detail": "disabled"}
    except Exception as e:
        log_service(f"Failed to disable service [{name}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))
