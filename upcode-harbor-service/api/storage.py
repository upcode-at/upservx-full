"""Storage / drive management routes."""

from fastapi import APIRouter, HTTPException

from lib.models import (
    DriveMountRequest, DriveUnmountRequest,
    DriveFormatRequest, ZFSPoolCreateRequest,
)
from lib.logger import log_storage
from handlers.storage import (
    get_drives, get_zfs_pools, mount_drive, unmount_drive,
    format_drive, create_zfs_pool,
)

router = APIRouter()


@router.get("/drives")
def list_drives():
    """List attached drives."""
    return {"drives": [d.dict() for d in get_drives()]}


@router.get("/drives/zfs")
def list_zfs():
    """List ZFS pools."""
    return {"pools": [p.dict() for p in get_zfs_pools()]}


@router.post("/drives/mount")
def api_mount_drive(payload: DriveMountRequest):
    """Mount a drive."""
    try:
        mount_drive(payload.device, payload.mountpoint)
        log_storage(f"Mounted [{payload.device}] → [{payload.mountpoint}]")
        return {"detail": "mounted"}
    except Exception as e:
        log_storage(f"Failed to mount [{payload.device}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/drives/unmount")
def api_unmount_drive(payload: DriveUnmountRequest):
    """Unmount a drive."""
    target = payload.mountpoint or payload.device
    try:
        unmount_drive(device=payload.device, mountpoint=payload.mountpoint)
        log_storage(f"Unmounted [{target}]")
        return {"detail": "unmounted"}
    except Exception as e:
        log_storage(f"Failed to unmount [{target}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/drives/format")
def api_format_drive(payload: DriveFormatRequest):
    """Format a drive. The device must be unmounted."""
    try:
        format_drive(payload.device, payload.filesystem, payload.label)
        log_storage(f"Formatted [{payload.device}] as {payload.filesystem}")
        return {"detail": "formatted"}
    except Exception as e:
        log_storage(f"Failed to format [{payload.device}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/drives/zfs")
def api_create_zfs(payload: ZFSPoolCreateRequest):
    """Create a new ZFS pool."""
    try:
        create_zfs_pool(payload.name, payload.devices, payload.raid)
        log_storage(f"Created ZFS pool [{payload.name}] ({payload.raid})")
        return {"detail": "created"}
    except Exception as e:
        log_storage(f"Failed to create ZFS pool [{payload.name}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))
