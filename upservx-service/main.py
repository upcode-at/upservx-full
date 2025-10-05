"""
UpservX - Server Management API

A comprehensive server management API built with FastAPI providing
container management, system monitoring, and server administration.
"""

from fastapi import FastAPI, Request, Response, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import base64
import pam
import uvicorn

# Import models
from models import (
    VirtualMachineCreate, VirtualMachineUpdate,
    DriveMountRequest, DriveFormatRequest, ZFSPoolCreateRequest,
    UserCreateModel, UserUpdateModel, GroupCreateModel, GroupUpdateModel, SSHKeyListModel,
    ISODownloadRequest, NetworkSettingsModel, SettingsModel
)

# Import utilities
from system_utils import collect_metrics
from storage import get_drives, get_zfs_pools, mount_drive, format_drive, create_zfs_pool
from network import get_network_interfaces, load_network_settings, save_network_settings
from users import (
    list_system_users, list_system_groups, create_user, update_user, delete_user,
    create_group, update_group, delete_group, read_authorized_keys, write_authorized_keys
)
from services import list_systemd_services, start_service, stop_service, enable_service, disable_service
from settings import load_settings, save_settings, apply_system_settings, generate_api_key, get_log_files, read_log_file
from vms import list_vms_with_status, create_vm, update_vm, start_vm, shutdown_vm, delete_vm
from isos import get_iso_files, download_iso, save_uploaded_iso, delete_iso, get_iso_path, get_iso_dir

# Import API routes
from api.system import router as system_router
from api.containers import router as containers_router
from api.images import router as images_router


app = FastAPI(
    title="UpservX API",
    description="Server Management API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pam_auth = pam.pam()


@app.middleware("http")
async def pam_auth_middleware(request: Request, call_next):
    """Authentication middleware using PAM or API key."""
    if request.method == "OPTIONS":
        return await call_next(request)
    
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return Response(status_code=401, headers={"WWW-Authenticate": "Basic"})
    
    try:
        scheme, credentials = auth_header.split(" ", 1)
        scheme = scheme.lower()
        
        if scheme == "basic":
            decoded = base64.b64decode(credentials).decode()
            username, password = decoded.split(":", 1)
            if not pam_auth.authenticate(username, password):
                return Response(status_code=401, headers={"WWW-Authenticate": "Basic"})
            request.state.user = username
        elif scheme == "bearer":
            settings = load_settings()
            if not settings.api_key or credentials.strip() != settings.api_key:
                return Response(status_code=401, headers={"WWW-Authenticate": "Basic"})
            request.state.user = "api-key"
        else:
            raise ValueError
    except Exception:
        return Response(status_code=401, headers={"WWW-Authenticate": "Basic"})
    
    response = await call_next(request)
    return response


# Include API routers
app.include_router(system_router)
app.include_router(containers_router)
app.include_router(images_router)


# ISO Management Routes
@app.get("/isos")
def list_isos():
    """List available ISO files."""
    return {"isos": [iso.dict() for iso in get_iso_files()]}


@app.post("/isos/download")
def download_iso_endpoint(payload: ISODownloadRequest):
    """Download an ISO file from a URL."""
    try:
        info = download_iso(payload.url, payload.name)
        return info.dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/isos")
async def upload_iso(file: UploadFile = File(...)):
    """Upload a new ISO file."""
    filename = file.filename or "upload.iso"
    content = await file.read()
    
    try:
        info = save_uploaded_iso(content, filename)
        return info.dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/isos/{name}")
def delete_iso_endpoint(name: str):
    """Delete an ISO file."""
    try:
        delete_iso(name)
        return {"detail": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/isos/{name}/file")
def download_iso_file(name: str):
    """Download an ISO file."""
    try:
        path = get_iso_path(name)
        return FileResponse(path, filename=name, media_type="application/octet-stream")
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


# Virtual Machine Routes
@app.get("/vms")
def list_vms():
    """List virtual machines."""
    existing = list_vms_with_status()
    return [vm.dict() for vm in existing]


@app.post("/vms")
def create_vm_endpoint(payload: VirtualMachineCreate):
    """Create a new virtual machine."""
    try:
        vm = create_vm(payload.name, payload.cpu, payload.memory, payload.iso, payload.disks, get_iso_dir())
        return vm.dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.patch("/vms/{name}")
def update_vm_endpoint(name: str, payload: VirtualMachineUpdate):
    """Update virtual machine configuration."""
    try:
        vm = update_vm(name, payload.cpu, payload.memory, payload.iso, payload.add_disks, get_iso_dir())
        return vm.dict()
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/vms/{name}/start")
def start_vm_endpoint(name: str):
    """Start a virtual machine."""
    try:
        start_vm(name)
        return {"detail": "started"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/vms/{name}/shutdown")
def shutdown_vm_endpoint(name: str):
    """Shutdown a virtual machine."""
    try:
        shutdown_vm(name)
        return {"detail": "shutting down"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/vms/{name}")
def delete_vm_endpoint(name: str):
    """Delete a virtual machine."""
    try:
        delete_vm(name)
        return {"detail": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Network Routes
@app.get("/network/interfaces")
def list_network_interfaces():
    """List network interfaces."""
    return {"interfaces": [i.dict() for i in get_network_interfaces()]}


@app.get("/network/settings")
def get_network_settings():
    """Get network settings."""
    return load_network_settings().dict()


@app.post("/network/settings")
def update_network_settings(payload: NetworkSettingsModel):
    """Update network settings."""
    save_network_settings(payload)
    return {"detail": "saved"}


# Storage Routes
@app.get("/drives")
def list_drives():
    """List storage drives."""
    return {"drives": [d.dict() for d in get_drives()]}


@app.get("/drives/zfs")
def list_zfs_pools():
    """List ZFS pools."""
    return {"pools": [p.dict() for p in get_zfs_pools()]}


@app.post("/drives/mount")
def mount_drive_endpoint(req: DriveMountRequest):
    """Mount a storage drive."""
    try:
        mount_drive(req.device, req.mountpoint)
        return {"detail": "mounted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/drives/format")
def format_drive_endpoint(req: DriveFormatRequest):
    """Format a storage drive."""
    try:
        format_drive(req.device, req.filesystem, req.label)
        return {"detail": "formatted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/drives/zfs")
def create_zfs_pool_endpoint(req: ZFSPoolCreateRequest):
    """Create a new ZFS pool."""
    try:
        create_zfs_pool(req.name, req.devices, req.raid)
        return {"detail": "created"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# User Management Routes
@app.get("/users")
def api_list_users(limit: int = 20, offset: int = 0):
    """List system users."""
    all_users = list_system_users()
    total = len(all_users)
    paginated = all_users[offset : offset + limit]
    return {"total": total, "users": [u.dict() for u in paginated]}


@app.post("/users")
def api_create_user(payload: UserCreateModel):
    """Create a new user."""
    try:
        create_user(payload.username, payload.password, payload.groups, payload.shell)
        return {"detail": "created"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/users/{username}")
def api_update_user(username: str, payload: UserUpdateModel):
    """Update a user."""
    try:
        update_user(username, payload.shell, payload.groups)
        return {"detail": "updated"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/users/{username}")
def api_delete_user(username: str):
    """Delete a user."""
    try:
        delete_user(username)
        return {"detail": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/users/{username}/keys")
def api_get_user_keys(username: str):
    """Get SSH keys for a user."""
    return {"keys": read_authorized_keys(username)}


@app.put("/users/{username}/keys")
def api_update_user_keys(username: str, payload: SSHKeyListModel):
    """Update SSH keys for a user."""
    keys = [k.strip() for k in payload.keys if k.strip()]
    if len(keys) > 3:
        raise HTTPException(status_code=400, detail="maximum 3 keys allowed")
    
    try:
        write_authorized_keys(username, keys)
        return {"detail": "saved"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Group Management Routes
@app.get("/groups")
def api_list_groups(limit: int = 20, offset: int = 0):
    """List system groups."""
    all_groups = list_system_groups()
    total = len(all_groups)
    paginated = all_groups[offset : offset + limit]
    return {"total": total, "groups": [g.dict() for g in paginated]}


@app.post("/groups")
def api_create_group(payload: GroupCreateModel):
    """Create a new group."""
    try:
        create_group(payload.name, payload.members)
        return {"detail": "created"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/groups/{name}")
def api_update_group(name: str, payload: GroupUpdateModel):
    """Update a group."""
    try:
        update_group(name, payload.members)
        return {"detail": "updated"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/groups/{name}")
def api_delete_group(name: str):
    """Delete a group."""
    try:
        delete_group(name)
        return {"detail": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Service Management Routes
@app.get("/services")
def api_list_services():
    """List system services."""
    return {"services": list_systemd_services()}


@app.post("/services/{name}/start")
def api_start_service(name: str):
    """Start a service."""
    try:
        start_service(name)
        return {"detail": "started"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/services/{name}/stop")
def api_stop_service(name: str):
    """Stop a service."""
    try:
        stop_service(name)
        return {"detail": "stopped"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/services/{name}/enable")
def api_enable_service(name: str):
    """Enable a service."""
    try:
        enable_service(name)
        return {"detail": "enabled"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/services/{name}/disable")
def api_disable_service(name: str):
    """Disable a service."""
    try:
        disable_service(name)
        return {"detail": "disabled"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Log Management Routes
@app.get("/logs")
def api_list_logs():
    """List available log files."""
    return {"logs": get_log_files()}


@app.get("/logs/{name}")
def api_get_log(name: str, lines: int = 100):
    """Get log file content."""
    try:
        content = read_log_file(name, lines)
        return Response(content, media_type="text/plain")
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


# Settings Routes
@app.get("/settings")
def get_settings():
    """Get system settings."""
    return load_settings().dict()


@app.post("/settings")
def update_settings(payload: SettingsModel):
    """Update system settings."""
    save_settings(payload)
    apply_system_settings(payload)
    return {"detail": "saved"}


@app.post("/settings/api-key")
def generate_api_key_endpoint():
    """Generate a new API key."""
    api_key = generate_api_key()
    return {"api_key": api_key}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)