"""
UpservX - Server Management API

A comprehensive server management API built with FastAPI providing
container management, system monitoring, and server administration.
"""

from fastapi import FastAPI, Request, Response, HTTPException, UploadFile, File, WebSocket
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketDisconnect
from typing import List, Optional
import base64
import pam
import uvicorn
import os
import subprocess
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import models
from models import (
    VirtualMachineCreate, VirtualMachineUpdate,
    DriveMountRequest, DriveFormatRequest, ZFSPoolCreateRequest,
    UserCreateModel, UserUpdateModel, GroupCreateModel, GroupUpdateModel, SSHKeyListModel,
    ISODownloadRequest, NetworkSettingsModel, SettingsModel,
    InterfaceConfigModel,
    BackupServer, BackupServerCreate, BackupServerUpdate,
    BackupJob, BackupJobCreate, BackupJobUpdate,
    BackupInstance, BackupExecuteRequest, BackupRestoreRequest,
    BackupListResponse, BackupServerInfo,
    ProxyConfigModel, ProxyConfigCreate, CertificateRequest, CertificateInfo
)

# Import utilities
from system_utils import collect_metrics, get_server_addresses
from storage import get_drives, get_zfs_pools, mount_drive, format_drive, create_zfs_pool
from network import get_network_interfaces, load_network_settings, save_network_settings, configure_interface
from users import (
    list_system_users, list_system_groups, create_user, update_user, delete_user,
    create_group, update_group, delete_group, read_authorized_keys, write_authorized_keys
)
from services import list_systemd_services, start_service, stop_service, enable_service, disable_service
from settings import (
    load_settings, save_settings, apply_system_settings, generate_api_key, get_log_files, read_log_file,
    save_vpn_ovpn, start_vpn, stop_vpn, get_vpn_status
)
from vms import list_vms_with_status, create_vm, update_vm, start_vm, shutdown_vm, delete_vm
from isos import get_iso_files, download_iso, save_uploaded_iso, delete_iso, get_iso_path, get_iso_dir
from backup_db import backup_db
from backup import backup_manager, BackupAuthConfig
from ssh_keys import ssh_key_manager
from crontab_manager import crontab_manager
from reverse_proxy import reverse_proxy_manager
from config_manager import get_config_manager

# Import API routes
from api.system import router as system_router
from api.containers import router as containers_router
from api.images import router as images_router
from api.firewall import router as firewall_router


app = FastAPI(
    title="UpservX API",
    description="Server Management API",
    version="1.0.0"
)

# Configure CORS. For development, set FRONTEND_ORIGINS env to a comma-separated
# list (e.g. "http://localhost:3000,http://127.0.0.1:3000"). If not set, automatically
# detect all server IP addresses, hostnames, and common dev origins.
frontend_origins = os.getenv("FRONTEND_ORIGINS")
if frontend_origins:
    allow_origins = [o.strip() for o in frontend_origins.split(",") if o.strip()]
else:
    # Automatically allow all server addresses with common ports
    allow_origins = get_server_addresses()

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
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
    
    # Skip authentication for backup endpoints during development
    # Note: This will be called directly at /backup/ or via reverse proxy
    if request.url.path.startswith("/backup/"):
        return await call_next(request)
    
    # Skip authentication for app store icons (public assets)
    if "/app-store/apps/" in request.url.path and request.url.path.endswith("/icon"):
        return await call_next(request)
    
    auth_header = request.headers.get("Authorization")
    # If Authorization header is missing, allow cookie named 'auth' to carry the Basic token
    if not auth_header:
        cookie_auth = request.cookies.get("auth")
        if cookie_auth:
            # cookie may contain the full header value or just the base64 token
            if cookie_auth.lower().startswith("basic "):
                auth_header = cookie_auth
            else:
                auth_header = f"Basic {cookie_auth}"

    if not auth_header:
        return Response(status_code=401)
    
    try:
        scheme, credentials = auth_header.split(" ", 1)
        scheme = scheme.lower()
        
        if scheme == "basic":
            decoded = base64.b64decode(credentials).decode()
            username, password = decoded.split(":", 1)
            if not pam_auth.authenticate(username, password):
                return Response(status_code=401)
            request.state.user = username
        elif scheme == "bearer":
            settings = load_settings()
            if not settings.api_key or credentials.strip() != settings.api_key:
                return Response(status_code=401)
            request.state.user = "api-key"
        else:
            raise ValueError
    except Exception:
        return Response(status_code=401)
    
    response = await call_next(request)
    return response



@app.post("/auth/login")
async def auth_login(payload: dict, request: Request):
    """Login endpoint to set a Basic auth cookie for client use.

    Accepts JSON {"username": "...", "password": "..."} and on success
    sets a cookie named `auth` containing the Basic token (base64). Cookie is HttpOnly.
    """
    username = payload.get("username")
    password = payload.get("password")
    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password required")

    # authenticate via PAM or API key
    try:
        if pam_auth.authenticate(username, password):
            token = base64.b64encode(f"{username}:{password}".encode()).decode()
            resp = Response(content={"detail": "logged_in"}, media_type="application/json")
            # For local development we set SameSite=Lax; do not set Secure so it works over HTTP
            resp.set_cookie("auth", token, httponly=True, samesite="Lax", max_age=3600)
            return resp
        else:
            raise HTTPException(status_code=401, detail="invalid credentials")
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@app.post("/auth/logout")
async def auth_logout():
    resp = Response(content={"detail": "logged_out"}, media_type="application/json")
    resp.delete_cookie("auth")
    return resp


# Include API routers
app.include_router(system_router)
app.include_router(containers_router)
app.include_router(images_router)
app.include_router(firewall_router)


# System Shell WebSocket
@app.websocket("/system/shell")
async def system_shell_websocket(websocket: WebSocket):
    """Provide interactive shell access to the system via websocket."""
    import asyncio
    import pty
    import os
    import fcntl
    import struct
    import termios
    
    await websocket.accept()
    
    try:
        # Create a pseudo-terminal
        master_fd, slave_fd = pty.openpty()
        
        # Start bash shell in the PTY
        pid = os.fork()
        
        if pid == 0:  # Child process
            os.close(master_fd)
            os.setsid()
            
            # Make the slave the controlling terminal
            fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)
            
            # Redirect stdin, stdout, stderr to slave
            os.dup2(slave_fd, 0)
            os.dup2(slave_fd, 1)
            os.dup2(slave_fd, 2)
            
            if slave_fd > 2:
                os.close(slave_fd)
            
            # Set TERM environment variable
            os.environ['TERM'] = 'xterm-256color'
            
            # Start bash
            os.execvp("bash", ["bash", "-l"])
        
        # Parent process
        os.close(slave_fd)
        
        # Set non-blocking mode
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        
        # Set terminal size (80x24 default)
        winsize = struct.pack("HHHH", 24, 80, 0, 0)
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
        
        # Task to read from PTY and send to websocket
        async def read_from_pty():
            while True:
                try:
                    await asyncio.sleep(0.01)
                    data = os.read(master_fd, 1024)
                    if data:
                        await websocket.send_text(data.decode('utf-8', errors='ignore'))
                except BlockingIOError:
                    pass
                except OSError:
                    break
                except WebSocketDisconnect:
                    break
        
        # Task to read from websocket and write to PTY
        async def write_to_pty():
            try:
                while True:
                    data = await websocket.receive_text()
                    os.write(master_fd, data.encode('utf-8'))
            except WebSocketDisconnect:
                pass
        
        # Run both tasks concurrently
        await asyncio.gather(
            read_from_pty(),
            write_to_pty(),
            return_exceptions=True
        )
        
    except Exception as e:
        await websocket.send_text(f"Error: {str(e)}\r\n")
    finally:
        try:
            os.close(master_fd)
            os.kill(pid, 9)
            os.waitpid(pid, 0)
        except:
            pass
        await websocket.close()


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


@app.post("/debug/echo")
async def debug_echo(request: Request):
    """Return request headers and a simple note to help debug whether Authorization header arrives."""
    try:
        headers = dict(request.headers)
    except Exception:
        headers = {}
    return {"note": "echo headers", "headers": headers}


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
        vm = create_vm(
            payload.name,
            payload.cpu,
            payload.memory,
            payload.iso,
            payload.disks,
            get_iso_dir(),
            network_bridge=getattr(payload, "network_bridge", "virbr0"),
            autostart=getattr(payload, "autostart", False),
            cloud_init=getattr(payload, "cloud_init", None),
        )
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


@app.post("/network/interfaces/{name}")
def api_configure_network_interface(name: str, payload: InterfaceConfigModel):
    """Configure a specific network interface."""
    try:
        configure_interface(name, payload)
        return {"detail": "applied"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


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


# VPN / OpenVPN Routes
@app.post("/settings/vpn/upload")
async def upload_vpn(file: UploadFile = File(...)):
    """Upload an OpenVPN .ovpn file to the server."""
    filename = file.filename or "client.ovpn"
    content = await file.read()
    try:
        path = save_vpn_ovpn(content, filename)
        return {"detail": "saved", "path": path}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/settings/vpn/file")
def download_vpn_file():
    """Download the stored .ovpn file if present."""
    try:
        status = get_vpn_status()
        if not status.get("ovpn_path"):
            raise Exception("ovpn file not found")
        return FileResponse(status.get("ovpn_path"), filename=os.path.basename(status.get("ovpn_path")), media_type="application/x-openvpn-profile")
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/settings/vpn/status")
def vpn_status():
    """Get current VPN status."""
    try:
        return get_vpn_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/settings/vpn/start")
def vpn_start():
    """Start the OpenVPN tunnel using the uploaded .ovpn file."""
    try:
        status = start_vpn()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/settings/vpn/stop")
def vpn_stop():
    """Stop the OpenVPN tunnel."""
    try:
        status = stop_vpn()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/settings/update")
async def run_update():
    """Run the install.sh script to update the system."""
    try:
        install_script = "/opt/upservx/install.sh"
        if not os.path.exists(install_script):
            raise HTTPException(status_code=404, detail="install.sh not found")
        
        # Run the install script with sudo
        result = subprocess.run(
            ["sudo", "bash", install_script],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )
        
        return {
            "detail": "update completed",
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="update timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Backup Management API Endpoints

@app.get("/backup/servers", response_model=List[BackupServer])
async def list_backup_servers():
    """List all backup servers from /etc/upservx configuration."""
    try:
        config = get_config_manager()
        servers = config.get_backup_servers()
        return [BackupServer(**server) for server in servers]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list backup servers: {str(e)}")


@app.post("/backup/servers", response_model=BackupServer)
async def create_backup_server(server: BackupServerCreate):
    """Create a new backup server in /etc/upservx configuration."""
    try:
        logger.info("Creating backup server...")
        config = get_config_manager()
        logger.info("Config manager obtained")
        
        server_data = server.model_dump()
        logger.info(f"Server data: {server_data}")
        
        # Handle SSH key if provided
        if server_data.get('ssh_key'):
            logger.info("SSH key provided, saving...")
            key_name = f"backup_{server_data['name'].replace(' ', '_').lower()}"
            key_path = config.save_ssh_key(key_name, server_data['ssh_key'])
            server_data['ssh_key_path'] = key_path
            del server_data['ssh_key']
            logger.info(f"SSH key saved to: {key_path}")
        
        # Store in /etc/upservx/backup_servers.json
        logger.info("Adding backup server to config...")
        created_server = config.add_backup_server(server_data)
        logger.info(f"Backup server created with ID: {created_server.get('id')}")
        
        return BackupServer(**created_server)
    except Exception as e:
        logger.error(f"Failed to create backup server: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to create backup server: {str(e)}")


@app.get("/backup/servers/{server_id}", response_model=BackupServer)
async def get_backup_server(server_id: int):
    """Get a specific backup server from /etc/upservx configuration."""
    try:
        config = get_config_manager()
        server = config.get_backup_server(server_id)
        if not server:
            raise HTTPException(status_code=404, detail="Backup server not found")
        return BackupServer(**server)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get backup server: {str(e)}")


@app.put("/backup/servers/{server_id}", response_model=BackupServer)
async def update_backup_server(server_id: int, server: BackupServerUpdate):
    """Update a backup server."""
    try:
        # Check if server exists
        existing_server = backup_db.get_backup_server(server_id)
        if not existing_server:
            raise HTTPException(status_code=404, detail="Backup server not found")
        
        # Convert to dict for database storage
        update_data = server.model_dump(exclude_unset=True)
        
        # Handle encryption of sensitive data
        if 'password' in update_data:
            update_data['password_encrypted'] = backup_manager.encrypt_sensitive_data(update_data['password'])
            del update_data['password']
        
        if 'ssh_key_passphrase' in update_data:
            update_data['ssh_key_passphrase_encrypted'] = backup_manager.encrypt_sensitive_data(update_data['ssh_key_passphrase'])
            del update_data['ssh_key_passphrase']
        
        # Handle SSH key update
        if 'ssh_key' in update_data:
            ssh_key_path = ssh_key_manager.store_ssh_key(
                f"backup_server_{existing_server['name']}", 
                update_data['ssh_key'],
                update_data.get('ssh_key_passphrase_encrypted')
            )
            update_data['ssh_key_path'] = ssh_key_path
            del update_data['ssh_key']
        
        success = backup_db.update_backup_server(server_id, update_data)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update server")
        
        # Get updated server
        updated_server = backup_db.get_backup_server(server_id)
        return BackupServer(**updated_server)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update backup server: {str(e)}")


@app.delete("/backup/servers/{server_id}")
async def delete_backup_server(server_id: int):
    """Delete a backup server from /etc/upservx configuration."""
    try:
        config = get_config_manager()
        success = config.delete_backup_server(server_id)
        if not success:
            raise HTTPException(status_code=404, detail="Backup server not found")
        return {"message": "Backup server deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete backup server: {str(e)}")


@app.post("/backup/servers/{server_id}/test")
async def test_backup_server(server_id: int):
    """Test connection to a backup server."""
    try:
        server = backup_db.get_backup_server(server_id)
        if not server:
            raise HTTPException(status_code=404, detail="Backup server not found")
        
        # Test the connection using backup manager
        if server['type'] == 'local':
            # Test local path accessibility
            import os
            if not os.path.exists(server['local_path']):
                os.makedirs(server['local_path'], exist_ok=True)
            success = os.path.isdir(server['local_path'])
        else:
            # Test remote connection
            auth_config = BackupAuthConfig(
                auth_type=server['auth_type'],
                username=server['username'],
                password=backup_manager.decrypt_sensitive_data(server.get('password_encrypted')) if server.get('password_encrypted') else None,
                ssh_key_path=server.get('ssh_key_path'),
                ssh_key_passphrase=backup_manager.decrypt_sensitive_data(server.get('ssh_key_passphrase_encrypted')) if server.get('ssh_key_passphrase_encrypted') else None
            )
            success = backup_manager.test_connection(server['host'], server['port'], auth_config)
        
        # Update server status
        new_status = 'connected' if success else 'error'
        backup_db.update_backup_server(server_id, {'status': new_status})
        
        return {"success": success, "status": new_status}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to test backup server: {str(e)}")


# Backup Jobs API

@app.get("/backup/jobs", response_model=List[BackupJob])
async def list_backup_jobs():
    """List all backup jobs."""
    try:
        jobs = backup_db.get_backup_jobs()
        return [BackupJob(**job) for job in jobs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list backup jobs: {str(e)}")


@app.post("/backup/jobs", response_model=BackupJob)
async def create_backup_job(job: BackupJobCreate):
    """Create a new backup job."""
    try:
        job_data = job.model_dump()
        job_id = backup_db.create_backup_job(job_data)
        
        created_job = backup_db.get_backup_job(job_id)
        if not created_job:
            raise HTTPException(status_code=500, detail="Failed to retrieve created job")
        
        # Add job to crontab for automatic scheduling
        success = crontab_manager.add_backup_job(
            job_id=job_id,
            schedule=created_job['schedule'],
            job_name=created_job['name']
        )
        
        if not success:
            # Log warning but don't fail the job creation
            import logging
            logging.warning(f"Failed to add backup job {job_id} to crontab")
        
        return BackupJob(**created_job)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create backup job: {str(e)}")


@app.get("/backup/jobs/{job_id}", response_model=BackupJob)
async def get_backup_job(job_id: int):
    """Get a specific backup job."""
    try:
        job = backup_db.get_backup_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Backup job not found")
        return BackupJob(**job)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get backup job: {str(e)}")


@app.put("/backup/jobs/{job_id}", response_model=BackupJob)
async def update_backup_job(job_id: int, job: BackupJobUpdate):
    """Update a backup job."""
    try:
        existing_job = backup_db.get_backup_job(job_id)
        if not existing_job:
            raise HTTPException(status_code=404, detail="Backup job not found")
        
        update_data = job.model_dump(exclude_unset=True)
        success = backup_db.update_backup_job(job_id, update_data)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update job")
        
        updated_job = backup_db.get_backup_job(job_id)
        return BackupJob(**updated_job)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update backup job: {str(e)}")


@app.delete("/backup/jobs/{job_id}")
async def delete_backup_job(job_id: int):
    """Delete a backup job."""
    try:
        # Remove from crontab first
        crontab_success = crontab_manager.remove_backup_job(job_id)
        if not crontab_success:
            import logging
            logging.warning(f"Failed to remove backup job {job_id} from crontab")
        
        # Delete from database
        success = backup_db.delete_backup_job(job_id)
        if not success:
            raise HTTPException(status_code=404, detail="Backup job not found")
        
        return {"message": "Backup job deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete backup job: {str(e)}")


@app.post("/backup/jobs/{job_id}/execute")
async def execute_backup_job(job_id: int):
    """Execute a backup job immediately."""
    try:
        job = backup_db.get_backup_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Backup job not found")
        
        # Get server from config manager (will decrypt password)
        config = get_config_manager()
        server = config.get_backup_server(job['server_id'])
        if not server:
            raise HTTPException(status_code=404, detail="Backup server not found")
        
        # Create backup instance
        import json
        instance_data = {
            'job_id': job_id,
            'server_id': job['server_id'],
            'backup_name': f"{job['name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'backup_path': '',  # Will be set by backup execution
            'backup_type': job['backup_type'],
            'targets': json.dumps(job['targets']) if isinstance(job['targets'], list) else job['targets'],
            'started': datetime.now().isoformat()
        }
        
        instance_id = backup_db.create_backup_instance(instance_data)
        
        # Execute the actual backup
        try:
            result = backup_manager.execute_backup(job, server)
            
            if result.get('success', False):
                # Update instance with success results
                backup_db.update_backup_instance(instance_id, {
                    'status': 'completed',
                    'backup_size': result.get('size', 0),
                    'backup_path': result.get('backup_path', ''),
                    'completed': datetime.now().isoformat(),
                    'error_message': None
                })
                return {
                    "message": "Backup job executed successfully", 
                    "instance_id": instance_id,
                    "backup_path": result.get('backup_path'),
                    "size": result.get('size', 0)
                }
            else:
                # Update instance with failure
                backup_db.update_backup_instance(instance_id, {
                    'status': 'failed',
                    'completed': datetime.now().isoformat(),
                    'error_message': result.get('error', 'Backup execution failed')
                })
                raise HTTPException(status_code=500, detail=f"Backup failed: {result.get('error')}")
                
        except Exception as backup_error:
            # Update instance with error
            backup_db.update_backup_instance(instance_id, {
                'status': 'failed',
                'completed': datetime.now().isoformat(),
                'error_message': str(backup_error)
            })
            raise HTTPException(status_code=500, detail=f"Backup execution error: {str(backup_error)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute backup job: {str(e)}")


# Backup Instances API

@app.get("/backup/instances", response_model=List[BackupInstance])
async def list_backup_instances(job_id: Optional[int] = None, server_id: Optional[int] = None, limit: Optional[int] = 100):
    """List backup instances with optional filtering."""
    try:
        instances = backup_db.get_backup_instances(job_id=job_id, server_id=server_id, limit=limit)
        return [BackupInstance(**instance) for instance in instances]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list backup instances: {str(e)}")


@app.get("/backup/instances/{instance_id}", response_model=BackupInstance)
async def get_backup_instance(instance_id: int):
    """Get a specific backup instance."""
    try:
        instance = backup_db.get_backup_instance(instance_id)
        if not instance:
            raise HTTPException(status_code=404, detail="Backup instance not found")
        return BackupInstance(**instance)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get backup instance: {str(e)}")


@app.delete("/backup/instances/{instance_id}")
async def delete_backup_instance(instance_id: int):
    """Delete a backup instance."""
    try:
        success = backup_db.delete_backup_instance(instance_id)
        if not success:
            raise HTTPException(status_code=404, detail="Backup instance not found")
        return {"message": "Backup instance deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete backup instance: {str(e)}")


@app.get("/backup/cron-jobs")
async def get_backup_cron_jobs():
    """Get all backup jobs currently scheduled in crontab."""
    try:
        cron_jobs = crontab_manager.list_backup_jobs()
        return cron_jobs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list cron jobs: {str(e)}")


# Reverse Proxy Management Routes

@app.get("/proxy/status")
def get_proxy_status():
    """Get Nginx installation and status."""
    return {
        "nginx": reverse_proxy_manager.get_nginx_status(),
        "certbot_installed": reverse_proxy_manager.check_certbot_installed()
    }





@app.get("/proxy/configs")
def list_proxy_configs():
    """List all reverse proxy configurations."""
    return {"configs": reverse_proxy_manager.list_proxy_configs()}


@app.post("/proxy/configs")
def create_proxy_config(config: ProxyConfigCreate):
    """Create a new reverse proxy configuration."""
    return reverse_proxy_manager.create_proxy_config(
        domain=config.domain,
        backend_host=config.backend_host,
        backend_port=config.backend_port,
        frontend_port=config.frontend_port,
        ssl_enabled=config.ssl_enabled,
        force_ssl=config.force_ssl
    )


@app.delete("/proxy/configs/{domain}")
def delete_proxy_config(domain: str):
    """Delete a reverse proxy configuration."""
    return reverse_proxy_manager.delete_proxy_config(domain)


@app.get("/proxy/certificates")
def list_certificates():
    """List all SSL certificates."""
    certs = reverse_proxy_manager.list_certificates()
    return {"certificates": certs}


@app.post("/proxy/certificates/obtain")
def obtain_certificate(request: CertificateRequest):
    """Obtain a new Let's Encrypt SSL certificate."""
    return reverse_proxy_manager.obtain_certificate(
        domain=request.domain,
        email=request.email
    )


@app.post("/proxy/certificates/renew")
def renew_certificates():
    """Renew all SSL certificates."""
    return reverse_proxy_manager.renew_certificates()


@app.delete("/proxy/certificates/{domain}")
def revoke_certificate(domain: str):
    """Revoke and delete an SSL certificate."""
    return reverse_proxy_manager.revoke_certificate(domain)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)