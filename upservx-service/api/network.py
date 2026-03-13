"""Network management routes."""

from fastapi import APIRouter, HTTPException

from lib.models import NetworkSettingsModel, InterfaceConfigModel
from lib.logger import log_network
from handlers.network import (
    get_network_interfaces, load_network_settings,
    save_network_settings, configure_interface,
)

router = APIRouter()


@router.get("/network/interfaces")
def list_network_interfaces():
    """List network interfaces."""
    return {"interfaces": [i.dict() for i in get_network_interfaces()]}


@router.get("/network/settings")
def get_network_settings():
    """Get network settings."""
    return load_network_settings().dict()


@router.post("/network/settings")
def update_network_settings(payload: NetworkSettingsModel):
    """Update network settings."""
    save_network_settings(payload)
    log_network("Network settings updated")
    return {"detail": "saved"}


@router.post("/network/interfaces/{name}")
def api_configure_network_interface(name: str, payload: InterfaceConfigModel):
    """Configure a specific network interface."""
    try:
        configure_interface(name, payload)
        log_network(f"Interface [{name}] configured")
        return {"detail": "applied"}
    except Exception as e:
        log_network(f"Failed to configure interface [{name}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))
