"""Virtual machine management routes."""

import os
import re

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from lib.models import VirtualMachineCreate, VirtualMachineUpdate
from lib.logger import log_vm
from lib.jobs import enqueue_job, get_job
from handlers.vms import (
    list_vms_with_status, create_vm, update_vm, start_vm, shutdown_vm,
    delete_vm, get_vnc_info, clone_vm, list_snapshots, create_snapshot,
    delete_snapshot, restore_snapshot, import_vm_ova,
    EXPORT_DIR, IMPORT_DIR,
)
from handlers.isos import get_iso_dir

router = APIRouter()


@router.get("/vms")
def list_vms():
    """List virtual machines."""
    return [vm.dict() for vm in list_vms_with_status()]


@router.post("/vms")
def create_vm_endpoint(payload: VirtualMachineCreate):
    """Create a new virtual machine."""
    try:
        vm = create_vm(
            payload.name, payload.cpu, payload.memory, payload.iso,
            payload.disks, get_iso_dir(),
            network_mode=getattr(payload, "network_mode", "nat"),
            bridge_interface=getattr(payload, "bridge_interface", None),
            vlan_id=getattr(payload, "vlan_id", None),
            network_name=getattr(payload, "network_name", None),
            autostart=getattr(payload, "autostart", False),
            cloud_init=getattr(payload, "cloud_init", None),
            storage_path=getattr(payload, "storage_path", None),
        )
        log_vm(f"Created VM [{payload.name}] ({payload.cpu} vCPU, {payload.memory} MB RAM)")
        return vm.dict()
    except Exception as e:
        log_vm(f"Failed to create VM [{payload.name}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/vms/{name}")
def update_vm_endpoint(name: str, payload: VirtualMachineUpdate):
    """Update virtual machine configuration."""
    try:
        vm = update_vm(
            name, payload.cpu, payload.memory, payload.iso, payload.add_disks,
            get_iso_dir(),
            autostart=getattr(payload, "autostart", None),
            remove_disks=getattr(payload, "remove_disks", []),
            network_mode=getattr(payload, "network_mode", None),
            bridge_interface=getattr(payload, "bridge_interface", None),
            vlan_id=getattr(payload, "vlan_id", None),
            network_name=getattr(payload, "network_name", None),
            storage_path=getattr(payload, "storage_path", None),
        )
        return vm.dict()
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/vms/{name}/start")
def start_vm_endpoint(name: str):
    """Start a virtual machine."""
    try:
        start_vm(name)
        log_vm(f"Started VM [{name}]")
        return {"detail": "started"}
    except Exception as e:
        log_vm(f"Failed to start VM [{name}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/vms/{name}/shutdown")
def shutdown_vm_endpoint(name: str):
    """Shutdown a virtual machine."""
    try:
        shutdown_vm(name)
        log_vm(f"Shutdown initiated for VM [{name}]")
        return {"detail": "shutting down"}
    except Exception as e:
        log_vm(f"Failed to shutdown VM [{name}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/vms/{name}/vnc")
def get_vm_vnc_info(name: str):
    """Get VNC connection info for a VM."""
    try:
        return get_vnc_info(name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/vms/{name}")
def delete_vm_endpoint(name: str):
    """Delete a virtual machine."""
    try:
        delete_vm(name)
        log_vm(f"Deleted VM [{name}]")
        return {"detail": "deleted"}
    except Exception as e:
        log_vm(f"Failed to delete VM [{name}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/vms/{name}/clone")
def clone_vm_endpoint(name: str, payload: dict):
    """Clone a virtual machine."""
    new_name = payload.get("new_name")
    storage_path = payload.get("storage_path")
    if not new_name:
        raise HTTPException(status_code=400, detail="new_name is required")
    try:
        vm = clone_vm(name, new_name, storage_path)
        log_vm(f"Cloned VM [{name}] to [{new_name}]")
        return vm.dict()
    except Exception as e:
        log_vm(f"Failed to clone VM [{name}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/vms/{name}/snapshots")
def list_vm_snapshots(name: str):
    """List all snapshots of a VM."""
    try:
        return list_snapshots(name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/vms/{name}/snapshots")
def create_vm_snapshot(name: str, payload: dict):
    """Create a new snapshot of a VM."""
    snapshot_name = payload.get("name")
    description = payload.get("description", "")
    if not snapshot_name:
        raise HTTPException(status_code=400, detail="name is required")
    try:
        result = create_snapshot(name, snapshot_name, description)
        log_vm(f"Created snapshot [{snapshot_name}] for VM [{name}]")
        return result
    except Exception as e:
        log_vm(f"Failed to create snapshot for VM [{name}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/vms/{name}/snapshots/{snapshot_name}")
def delete_vm_snapshot(name: str, snapshot_name: str):
    """Delete a snapshot."""
    try:
        delete_snapshot(name, snapshot_name)
        log_vm(f"Deleted snapshot [{snapshot_name}] from VM [{name}]")
        return {"detail": "deleted"}
    except Exception as e:
        log_vm(f"Failed to delete snapshot [{snapshot_name}] from VM [{name}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/vms/{name}/snapshots/{snapshot_name}/restore")
def restore_vm_snapshot(name: str, snapshot_name: str):
    """Revert a VM to a snapshot."""
    try:
        restore_snapshot(name, snapshot_name)
        log_vm(f"Restored VM [{name}] to snapshot [{snapshot_name}]")
        return {"detail": "restored"}
    except Exception as e:
        log_vm(f"Failed to restore VM [{name}] to snapshot [{snapshot_name}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/vms/{name}/export", status_code=202)
def export_vm_endpoint(name: str, payload: dict = {}):
    """Queue a VM export. The persistent worker performs the heavy work."""
    fmt = (payload or {}).get("format", "ova").lower()
    if fmt not in ("ova", "ovf"):
        raise HTTPException(status_code=400, detail="format must be 'ova' or 'ovf'")
    job = enqueue_job(
        "vm_export",
        {"name": name, "format": fmt},
        idempotency_key=f"vm-export:{name}:{fmt}",
        resource_type="vm_export",
        resource_id=name,
    )
    return {"detail": "queued", "persistent_job": job}


@router.get("/vms/exports/jobs/{job_id}")
def get_vm_export_job(job_id: str):
    """Return one VM export status to principals with VM read access."""
    job = get_job(job_id)
    if job is None or job.get("kind") != "vm_export":
        raise HTTPException(status_code=404, detail="VM export job not found")
    return job


@router.get("/vms/exports/{filename}")
def download_vm_export(filename: str):
    """Download a previously exported VM file."""
    if not re.match(r'^[\w\-. ]+$', filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    file_path = os.path.join(EXPORT_DIR, filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Export file not found")
    media_type = "application/x-tar" if filename.endswith(".ova") else "application/xml"
    return FileResponse(file_path, media_type=media_type, filename=filename)


@router.post("/vms/import")
async def import_vm_endpoint(
    file: UploadFile = File(...),
    name: str = "",
    network_mode: str = "nat",
    bridge_interface: str = "",
    vlan_id: int = 0,
    network_name: str = "",
    autostart: bool = False,
    storage_path: str = "",
):
    """Import a VM from an uploaded OVA or OVF file."""
    if not name.strip():
        raise HTTPException(status_code=400, detail="name is required")
    if not file.filename or not file.filename.lower().endswith((".ova", ".ovf")):
        raise HTTPException(status_code=400, detail="Only .ova or .ovf files are supported")

    os.makedirs(IMPORT_DIR, exist_ok=True)
    upload_path = os.path.join(IMPORT_DIR, f"upload_{name}{os.path.splitext(file.filename)[1].lower()}")
    try:
        with open(upload_path, "wb") as f:
            while chunk := await file.read(1 << 20):
                f.write(chunk)
        vm = import_vm_ova(
            source_path=upload_path,
            name=name.strip(),
            network_mode=network_mode or "nat",
            bridge_interface=bridge_interface or None,
            vlan_id=vlan_id if vlan_id > 0 else None,
            network_name=network_name or None,
            autostart=autostart,
            storage_path=storage_path or None,
        )
        log_vm(f"Imported VM [{name}] from uploaded file [{file.filename}]")
        return vm.dict()
    except Exception as e:
        log_vm(f"Failed to import VM [{name}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if os.path.isfile(upload_path):
            try:
                os.remove(upload_path)
            except Exception:
                pass
