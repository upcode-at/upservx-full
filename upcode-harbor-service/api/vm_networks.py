"""VM internal network management routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from handlers.vm_networks import (
    list_vm_networks,
    create_vm_network,
    delete_vm_network,
    start_vm_network,
    stop_vm_network,
)
from lib.logger import log_vm

router = APIRouter()


class VmNetworkCreate(BaseModel):
    name: str


@router.get("/vm-networks")
def list_networks():
    """List all libvirt virtual networks."""
    try:
        return list_vm_networks()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vm-networks")
def create_network(payload: VmNetworkCreate):
    """Create a new internal libvirt network."""
    try:
        result = create_vm_network(name=payload.name)
        log_vm(f"Network [{payload.name}] created via API")
        return result
    except Exception as e:
        log_vm(f"Failed to create network [{payload.name}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/vm-networks/{name}")
def delete_network(name: str):
    """Delete a libvirt network."""
    try:
        delete_vm_network(name)
        return {"detail": "deleted"}
    except Exception as e:
        log_vm(f"Failed to delete network [{name}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/vm-networks/{name}/start")
def start_network(name: str):
    """Start (activate) a defined but inactive libvirt network."""
    try:
        start_vm_network(name)
        return {"detail": "started"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/vm-networks/{name}/stop")
def stop_network(name: str):
    """Stop an active libvirt network."""
    try:
        stop_vm_network(name)
        return {"detail": "stopped"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
