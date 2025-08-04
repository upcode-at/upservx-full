from fastapi import FastAPI, HTTPException, WebSocket, UploadFile, File, Request
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import base64
import pam
import secrets
import psutil
import platform
import subprocess
import json
import time
import os
import shutil
import pty
import urllib.request
import urllib.parse
from datetime import datetime
from typing import List
import asyncio
import socket

from models import (
    Container,
    ContainerCreate,
    ISOInfo,
    ContainerImageInfo,
    LogInfo,
    DriveInfo,
    ZFSDeviceInfo,
    ZFSPoolInfo,
    NetworkInterfaceInfo,
    VirtualMachine,
    VirtualMachineCreate,
    VirtualMachineUpdate,
    ISODownloadRequest,
    ImagePullRequest,
    DriveMountRequest,
    DriveFormatRequest,
    ZFSPoolCreateRequest,
)
from settings import (
    load_settings,
    save_settings,
    load_network_settings,
    save_network_settings,
    ISO_DIR,
    SettingsModel,
    NetworkSettingsModel,
)
from users import (
    SystemUserModel,
    SystemGroupModel,
    UserCreateModel,
    UserUpdateModel,
    GroupCreateModel,
    GroupUpdateModel,
    SSHKeyListModel,
    list_system_users,
    list_system_groups,
    read_authorized_keys,
    write_authorized_keys,
)
from utils import (
    run_subprocess,
    parse_ports,
    parse_docker_size,
    guess_iso_info,
    get_iso_files,
    drive_type,
)

# Track last network counters for throughput calculation
_prev_net_io = psutil.net_io_counters()
_prev_net_time = time.time()


app = FastAPI()

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


@app.get("/")
def read_root():
    return {"detail": "ok"}

# Containers that are created via the API are stored here in-memory. Containers
# discovered from Docker, LXC or Kubernetes are queried on demand and not stored
# in this list.
containers: List[Container] = []

next_container_id = 1

VM_FILE = os.path.join(os.path.dirname(__file__), "vms.json")


def format_uptime(seconds: float) -> str:
    minutes, _ = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    return " ".join(parts) if parts else "0m"


def get_cpu_model() -> str:
    model = platform.processor()
    if not model:
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.lower().startswith("model name"):
                        model = line.split(":", 1)[1].strip()
                        break
        except FileNotFoundError:
            pass
    return model or "unknown"


def get_gpu_model() -> str:
    """Return the GPU model if available.

    The function first attempts to query NVIDIA GPUs using ``nvidia-smi``.  If no
    NVIDIA GPU is present or the command fails, it falls back to parsing the
    output of ``lshw -C display`` which works for a broader range of hardware
    including Intel and AMD GPUs.
    """

    # Try NVIDIA GPUs via nvidia-smi
    try:
        output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        if output:
            return output.splitlines()[0]
    except Exception:
        pass

    # Fall back to lshw which lists all display adapters
    try:
        output = subprocess.check_output(
            ["lshw", "-C", "display"],
            stderr=subprocess.DEVNULL,
        ).decode()
        for line in output.splitlines():
            line = line.strip()
            if line.lower().startswith("product:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass

    return "none"


def get_service_status(service: str) -> str:
    """Return 'running', 'stopped' or 'not found' for given service."""
    # Prefer systemctl if available
    if shutil.which("systemctl"):
        result = subprocess.run(
            ["systemctl", "is-active", service],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip() == "active":
            return "running"
        if result.returncode == 4 or "could not be found" in result.stderr:
            return "not found"
        return "stopped"

    # Fallback: check if binary exists and whether a process is running
    if shutil.which(service) is None:
        return "not found"
    for proc in psutil.process_iter(["name", "exe", "cmdline"]):
        try:
            if (
                proc.info.get("name") == service
                or (proc.info.get("exe") and os.path.basename(proc.info["exe"]) == service)
                or (
                    proc.info.get("cmdline")
                    and proc.info["cmdline"]
                    and os.path.basename(proc.info["cmdline"][0]) == service
                )
            ):
                return "running"
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return "stopped"


def list_systemd_services() -> list[dict[str, any]]:
    """Return a list of systemd services with status and enabled state."""
    services: list[dict[str, any]] = []
    if shutil.which("systemctl") is None:
        return services
    try:
        result = subprocess.run(
            ["systemctl", "list-unit-files", "--type=service", "--no-legend"],
            capture_output=True,
            text=True,
        )
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                name = parts[0]
                enabled = parts[1].lower().startswith("enabled")
                services.append(
                    {
                        "name": name,
                        "status": get_service_status(name),
                        "enabled": enabled,
                    }
                )
    except Exception:
        pass
    return services


def load_vms() -> List[VirtualMachine]:
    if os.path.exists(VM_FILE):
        try:
            with open(VM_FILE) as f:
                data = json.load(f)
            return [VirtualMachine(**vm) for vm in data]
        except Exception:
            return []
    return []


def save_vms(vms: List[VirtualMachine]) -> None:
    with open(VM_FILE, "w") as f:
        json.dump([vm.dict() for vm in vms], f)


def parse_virsh_list() -> dict[str, str]:
    statuses: dict[str, str] = {}
    if shutil.which("virsh") is None:
        return statuses
    result = subprocess.run(["virsh", "list", "--all"], capture_output=True, text=True)
    if result.returncode != 0:
        return statuses
    for line in result.stdout.splitlines()[2:]:
        parts = line.split()
        if len(parts) >= 3:
            statuses[parts[1]] = parts[2]
    return statuses



def get_docker_containers() -> List[Container]:
    """Return running Docker containers using the docker CLI."""
    if shutil.which("docker") is None:
        return []
    try:
        output = subprocess.check_output(
            [
                "docker",
                "ps",
                "-a",
                "--format",
                "{{.Names}}||{{.Image}}||{{.Status}}||{{.Ports}}||{{.RunningFor}}",
            ],
            text=True,
        ).strip()
    except Exception:
        return []

    containers_list = []
    for line in output.splitlines():
        parts = line.split("||")
        if len(parts) != 5:
            continue
        name, image, status, ports, running_for = parts
        containers_list.append(
            Container(
                id=0,
                name=name,
                type="Docker",
                status="running" if status.lower().startswith("up") else "stopped",
                image=image,
                ports=parse_ports(ports),
                mounts=[],
                envs=[],
                cpu=0.0,
                memory=0,
                created=running_for,
            )
        )
    return containers_list


def get_lxc_containers() -> List[Container]:
    """Return LXC/LXD containers using the lxc CLI if available."""
    if shutil.which("lxc") is None:
        return []
    try:
        output = subprocess.check_output(
            ["lxc", "list", "--format", "json"], text=True
        ).strip()
        data = json.loads(output)
    except Exception:
        return []

    containers_list = []
    for item in data:
        config = item.get("config", {})
        os_name = config.get("image.os", "")
        release = config.get("image.release", "")
        image = f"{os_name} {release}".strip()
        containers_list.append(
            Container(
                id=0,
                name=item.get("name", ""),
                type="LXC",
                status=item.get("status", "").lower(),
                image=image,
                ports=[],
                mounts=[],
                envs=[],
                cpu=0.0,
                memory=0,
                created=item.get("created_at", ""),
            )
        )
    return containers_list


def get_k8s_pods() -> List[Container]:
    """Return Kubernetes pods using kubectl if available."""
    if shutil.which("kubectl") is None:
        return []
    try:
        output = subprocess.check_output(
            ["kubectl", "get", "pods", "-A", "-o", "json"], text=True
        ).strip()
        data = json.loads(output)
    except Exception:
        return []

    containers_list = []
    for item in data.get("items", []):
        metadata = item.get("metadata", {})
        status = item.get("status", {})
        containers_list.append(
            Container(
                id=0,
                name=metadata.get("name", ""),
                type="Kubernetes",
                status=status.get("phase", "").lower(),
                image="",
                ports=[],
                mounts=[],
                envs=[],
                cpu=0.0,
                memory=0,
                created=metadata.get("creationTimestamp", ""),
            )
        )
    return containers_list


def get_docker_images() -> List[str]:
    """Return available Docker images using the docker CLI."""
    if shutil.which("docker") is None:
        return []
    try:
        output = subprocess.check_output(
            ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
            text=True,
        ).strip()
    except Exception:
        return []
    images = [line for line in output.splitlines() if line and not line.startswith("<none>")]
    return images



def get_docker_image_details() -> List[ContainerImageInfo]:
    if shutil.which("docker") is None:
        return []
    try:
        output = subprocess.check_output(
            [
                "docker",
                "images",
                "--format",
                "{{.Repository}}||{{.Tag}}||{{.ID}}||{{.Size}}||{{.CreatedSince}}",
            ],
            text=True,
        ).strip()
    except Exception:
        return []
    images: List[ContainerImageInfo] = []
    for idx, line in enumerate(output.splitlines(), start=1):
        parts = line.split("||")
        if len(parts) != 5:
            continue
        repo, tag, image_id, size, created = parts
        images.append(
            ContainerImageInfo(
                id=idx,
                repository=repo,
                tag=tag,
                imageId=image_id,
                size=parse_docker_size(size),
                created=created,
                used=True,
                pulls=0,
            )
        )
    return images


def get_lxc_image_details() -> List[ContainerImageInfo]:
    if shutil.which("lxc") is None:
        return []
    try:
        output = subprocess.check_output(["lxc", "image", "list", "--format", "json"], text=True).strip()
        data = json.loads(output)
    except Exception:
        return []
    images: List[ContainerImageInfo] = []
    for idx, img in enumerate(data, start=1):
        alias = ""
        aliases = img.get("aliases", [])
        if aliases:
            alias = aliases[0].get("name", "")
        repository = alias
        tag = ""
        if "/" in alias:
            repository, tag = alias.split("/", 1)
        images.append(
            ContainerImageInfo(
                id=idx,
                repository=repository,
                tag=tag,
                imageId=img.get("fingerprint", ""),
                size=round(img.get("size", 0) / (1024 ** 2), 2),
                created=img.get("uploaded_at", ""),
                used=False,
                pulls=0,
            )
        )
    return images


def get_lxc_images() -> List[str]:
    """Return available LXC images using the lxc CLI."""
    if shutil.which("lxc") is None:
        return []
    try:
        output = subprocess.check_output(["lxc", "image", "list", "--format", "json"], text=True).strip()
        data = json.loads(output)
    except Exception:
        return []

    images = []
    for img in data:
        aliases = img.get("aliases", [])
        if aliases:
            images.append(aliases[0].get("name", ""))
        else:
            images.append(img.get("fingerprint", ""))
    return images





def get_zfs_pools() -> List[ZFSPoolInfo]:
    """Return a list of ZFS pools with their member devices and usage."""
    if shutil.which("zpool") is None:
        return []

    size_info: dict[str, dict[str, int]] = {}
    result = subprocess.run(
        ["zpool", "list", "-H", "-p", "-o", "name,size,alloc,free"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4:
                name, size, alloc, free = parts[:4]
                size_info[name] = {
                    "size": int(size),
                    "used": int(alloc),
                    "available": int(free),
                }

    mountpoints: dict[str, str] = {}
    zfs_res = subprocess.run(
        ["zfs", "list", "-H", "-o", "name,mountpoint"],
        capture_output=True,
        text=True,
    )
    if zfs_res.returncode == 0:
        for line in zfs_res.stdout.splitlines():
            try:
                name, mnt = line.split("\t")
            except ValueError:
                continue
            if "/" not in name:
                mountpoints[name] = mnt

    status = subprocess.run(["zpool", "status"], capture_output=True, text=True)
    if status.returncode != 0:
        return []

    pools: List[ZFSPoolInfo] = []
    lines = status.stdout.splitlines()
    pool: dict | None = None
    in_config = False
    for line in lines:
        if line.startswith("  pool:"):
            if pool:
                pools.append(ZFSPoolInfo(**pool))
            name = line.split()[1]
            info = size_info.get(name, {"size": 0, "used": 0, "available": 0})
            pool = {
                "name": name,
                "devices": [],
                "type": "stripe",
                "size": round(info["size"] / (1024 ** 3)),
                "used": round(info["used"] / (1024 ** 3)),
                "available": round(info["available"] / (1024 ** 3)),
                "mountpoint": mountpoints.get(name, ""),
            }
            in_config = False
        elif pool and line.startswith(" state:"):
            pass
        elif pool and line.startswith("config:"):
            in_config = True
        elif pool and in_config:
            stripped = line.strip()
            if not stripped or stripped.startswith("NAME"):
                continue
            parts = stripped.split()
            token = parts[0]
            state = parts[1] if len(parts) > 1 else ""
            if token == pool["name"]:
                continue
            if token.startswith("mirror") or token.startswith("raidz"):
                pool["type"] = token.split("-")[0]
                continue
            device = token
            if not token.startswith("/"):
                device = f"/dev/{token}"
            pool["devices"].append({"path": device, "status": state})
        if pool and line.startswith("errors:"):
            pass
    if pool:
        pools.append(ZFSPoolInfo(**pool))
    return pools


def get_drives() -> List[DriveInfo]:
    """Return information for all physical drives including unmounted ones."""
    drives: List[DriveInfo] = []
    try:
        output = subprocess.check_output(
            ["lsblk", "-b", "-J", "-o", "NAME,TYPE,SIZE,FSTYPE,MOUNTPOINT"],
            text=True,
        )
        data = json.loads(output)
    except Exception:
        data = {"blockdevices": []}

    def add_device(node: dict) -> None:
        if node.get("type") not in {"disk", "part"}:
            for child in node.get("children", []):
                add_device(child)
            return
        if node.get("type") == "disk" and node.get("children"):
            for child in node.get("children", []):
                add_device(child)
            return
        name = node.get("name")
        if not name:
            return
        dev = f"/dev/{name}"
        if dev.startswith("/dev/loop"):
            return
        mountpoint = node.get("mountpoint") or ""
        try:
            size = int(node.get("size", 0))
        except Exception:
            size = 0
        if size <= 0:
            return
        usage = None
        if mountpoint:
            try:
                usage = psutil.disk_usage(mountpoint)
            except Exception:
                pass
        drives.append(
            DriveInfo(
                device=dev,
                name=name,
                type=drive_type(dev),
                size=round(size / (1024 ** 3)),
                used=round((usage.used if usage else 0) / (1024 ** 3)),
                available=round((usage.free if usage else 0) / (1024 ** 3)),
                filesystem=node.get("fstype") or "",
                mountpoint=mountpoint,
                mounted=bool(mountpoint),
            )
        )
        for child in node.get("children", []):
            add_device(child)

    for dev in data.get("blockdevices", []):
        add_device(dev)

    # Remove devices that are part of ZFS pools
    for pool in get_zfs_pools():
        for dev in pool.devices:
            drives = [d for d in drives if d.device != dev.path]

    unique = {}
    for d in drives:
        if d.device not in unique:
            unique[d.device] = d
    return list(unique.values())


def _format_bytes(num: int) -> str:
    step = 1024.0
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < step:
            return f"{num:.1f} {unit}"
        num /= step
    return f"{num:.1f} PB"


def _infer_iface_type(name: str) -> str:
    if name.startswith(("wl", "wifi")):
        return "WiFi"
    if name.startswith("br"):
        return "Bridge"
    if name.startswith(("docker", "veth")):
        return "Virtual"
    return "Ethernet"


def _default_gateways() -> dict[str, str]:
    gateways: dict[str, str] = {}
    try:
        output = subprocess.check_output(["ip", "route", "show", "default"], text=True)
        for line in output.splitlines():
            parts = line.split()
            if not parts or parts[0] != "default":
                continue
            gw = parts[2] if len(parts) >= 3 else "-"
            if "dev" in parts:
                idx = parts.index("dev")
                if idx + 1 < len(parts):
                    gateways[parts[idx + 1]] = gw
    except Exception:
        pass
    return gateways


def get_network_interfaces() -> List[NetworkInterfaceInfo]:
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    io_counters = psutil.net_io_counters(pernic=True)
    gateways = _default_gateways()

    interfaces: List[NetworkInterfaceInfo] = []
    for name, addr_list in addrs.items():
        stat = stats.get(name)
        if not stat:
            continue
        ip = "-"
        netmask = "-"
        mac = "-"
        for addr in addr_list:
            if addr.family == socket.AF_INET:
                ip = addr.address
                netmask = addr.netmask or "-"
            elif addr.family == psutil.AF_LINK or getattr(socket, "AF_PACKET", 17) == addr.family:
                mac = addr.address
        io = io_counters.get(name)
        rx = _format_bytes(io.bytes_recv) if io else "0 B"
        tx = _format_bytes(io.bytes_sent) if io else "0 B"
        speed = f"{stat.speed} Mbps" if stat.speed > 0 else "-"
        interfaces.append(
            NetworkInterfaceInfo(
                name=name,
                type=_infer_iface_type(name),
                status="up" if stat.isup else "down",
                ip=ip,
                netmask=netmask,
                gateway=gateways.get(name, "-"),
                mac=mac,
                speed=speed,
                rx=rx,
                tx=tx,
            )
        )
    return interfaces


def find_container_type(name: str) -> str | None:
    """Detect which container backend knows a container by this name."""
    for c in get_docker_containers():
        if c.name == name:
            return "docker"
    for c in get_lxc_containers():
        if c.name == name:
            return "lxc"
    for c in get_k8s_pods():
        if c.name == name:
            return "k8s"
    for c in containers:
        if c.name == name:
            return "api"
    return None


def collect_metrics() -> dict:
    cpu_percent = psutil.cpu_percent(interval=None)
    cpu_count = psutil.cpu_count(logical=False) or psutil.cpu_count()
    virt = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    global _prev_net_io, _prev_net_time
    net = psutil.net_io_counters()
    now = time.time()
    in_rate = 0.0
    out_rate = 0.0
    if _prev_net_io:
        delta = max(now - _prev_net_time, 1e-6)
        in_rate = (net.bytes_recv - _prev_net_io.bytes_recv) / delta
        out_rate = (net.bytes_sent - _prev_net_io.bytes_sent) / delta
    _prev_net_io = net
    _prev_net_time = now
    uptime_seconds = time.time() - psutil.boot_time()

    services_info = [
        {"name": "Docker", "service": "docker", "port": 2376},
        {"name": "Kubernetes", "service": "k3s", "port": 6443},
        {"name": "LXC", "service": "lxd", "port": None},
        {"name": "SSH", "service": "sshd", "port": _system_ssh_port()},
        {"name": "ZFS", "service": "zfs", "port": None},
    ]

    services = [
        {
            "name": s["name"],
            "status": get_service_status(s["service"]),
            "port": s["port"],
        }
        for s in services_info
    ]

    return {
        "cpu": {
            "usage": cpu_percent,
            "cores": cpu_count,
            "model": get_cpu_model(),
        },
        "memory": {
            "used": round(virt.used / (1024 ** 3), 2),
            "total": round(virt.total / (1024 ** 3), 2),
            "usage": virt.percent,
        },
        "storage": {
            "used": round(disk.used / (1024 ** 3), 2),
            "total": round(disk.total / (1024 ** 3), 2),
            "usage": disk.percent,
        },
        "network": {
            "in": round(in_rate / (1024 ** 2), 2),
            "out": round(out_rate / (1024 ** 2), 2),
        },
        "gpu": get_gpu_model(),
        "uptime": format_uptime(uptime_seconds),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "services": services,
    }


@app.get("/containers")
def list_containers():
    all_containers: List[Container] = []
    all_containers.extend(get_docker_containers())
    all_containers.extend(get_lxc_containers())
    all_containers.extend(get_k8s_pods())
    all_containers.extend(containers)

    # Assign stable sequential ids for the response
    for idx, c in enumerate(all_containers, start=1):
        c.id = idx
    return [c.dict() for c in all_containers]


@app.get("/images")
def list_images(type: str, full: bool = False):
    """Return available container images for the given type."""
    type_lower = type.lower()
    if full:
        if type_lower in {"docker", "kubernetes"}:
            return {"images": [img.dict() for img in get_docker_image_details()]}
        if type_lower == "lxc":
            return {"images": [img.dict() for img in get_lxc_image_details()]}
    else:
        if type_lower in {"docker", "kubernetes"}:
            return {"images": get_docker_images()}
        if type_lower == "lxc":
            return {"images": get_lxc_images()}
    raise HTTPException(status_code=400, detail="unknown container type")


@app.get("/isos")
def list_isos():
    return {"isos": [iso.dict() for iso in get_iso_files()]}



@app.post("/isos/download")
def download_iso(payload: ISODownloadRequest):
    """Download an ISO file from a URL and store it."""
    if not payload.url:
        raise HTTPException(status_code=400, detail="url required")
    filename = payload.name or os.path.basename(urllib.parse.urlparse(payload.url).path) or "download.iso"
    if not filename.lower().endswith(".iso"):
        filename += ".iso"
    dest = os.path.join(ISO_DIR, filename)
    try:
        with urllib.request.urlopen(payload.url) as resp, open(dest, "wb") as out:
            shutil.copyfileobj(resp, out)
    except Exception as e:
        if os.path.exists(dest):
            os.remove(dest)
        raise HTTPException(status_code=400, detail=str(e))
    stat = os.stat(dest)
    typ, version, arch = guess_iso_info(filename)
    info = ISOInfo(
        id=0,
        name=filename,
        size=round(stat.st_size / (1024 ** 3), 1),
        type=typ,
        version=version,
        architecture=arch,
        created=datetime.fromtimestamp(stat.st_mtime).date().isoformat(),
        used=False,
        path=dest,
    )
    return info.dict()


@app.post("/isos")
async def upload_iso(file: UploadFile = File(...)):
    """Upload a new ISO file."""
    filename = os.path.basename(file.filename)
    if not filename.lower().endswith(".iso"):
        raise HTTPException(status_code=400, detail="invalid iso file")
    dest = os.path.join(ISO_DIR, filename)
    with open(dest, "wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    stat = os.stat(dest)
    typ, version, arch = guess_iso_info(filename)
    info = ISOInfo(
        id=0,
        name=filename,
        size=round(stat.st_size / (1024 ** 3), 1),
        type=typ,
        version=version,
        architecture=arch,
        created=datetime.fromtimestamp(stat.st_mtime).date().isoformat(),
        used=False,
        path=dest,
    )
    return info.dict()


@app.delete("/isos/{name}")
def delete_iso(name: str):
    path = os.path.join(ISO_DIR, name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="iso not found")
    os.remove(path)
    return {"detail": "deleted"}


@app.get("/isos/{name}/file")
def download_iso_file(name: str):
    path = os.path.join(ISO_DIR, name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="iso not found")
    return FileResponse(path, filename=name, media_type="application/octet-stream")



@app.post("/images/pull")
def pull_image(payload: ImagePullRequest):
    """Pull a container image via Docker or LXC."""
    if not payload.image:
        raise HTTPException(status_code=400, detail="image required")

    typ = (payload.type or "docker").lower()
    if typ in {"docker", "kubernetes"}:
        if shutil.which("docker") is None:
            raise HTTPException(status_code=404, detail="docker not installed")
        image = payload.image
        if payload.registry:
            image = f"{payload.registry}/{image}"
        result = subprocess.run(["docker", "pull", image], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to pull")
        return {"detail": "pulled"}
    if typ == "lxc":
        if shutil.which("lxc") is None:
            raise HTTPException(status_code=404, detail="lxc not installed")
        remote = payload.registry or "images"
        alias = payload.image.split("/")[0]
        result = subprocess.run([
            "lxc",
            "image",
            "copy",
            f"{remote}:{payload.image}",
            "local:",
            "--alias",
            alias,
        ], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to pull")
        return {"detail": "pulled"}
    raise HTTPException(status_code=400, detail="unknown container type")


@app.delete("/images/{image}")
def delete_image(image: str, type: str):
    type_lower = type.lower()
    if type_lower in {"docker", "kubernetes"}:
        if shutil.which("docker") is None:
            raise HTTPException(status_code=404, detail="docker not installed")
        result = subprocess.run(["docker", "rmi", image], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to delete")
        return {"detail": "deleted"}
    if type_lower == "lxc":
        if shutil.which("lxc") is None:
            raise HTTPException(status_code=404, detail="lxc not installed")
        result = subprocess.run(["lxc", "image", "delete", image], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to delete")
        return {"detail": "deleted"}
    raise HTTPException(status_code=400, detail="unknown container type")


@app.post("/containers")
def create_container(payload: ContainerCreate):
    """Create a new container via Docker, LXC or Kubernetes if available."""
    typ = payload.type.lower()
    if typ == "docker":
        if shutil.which("docker") is None:
            raise HTTPException(status_code=404, detail="docker not installed")
        cmd = ["docker", "run", "-d", "--name", payload.name]
        for p in payload.ports:
            cmd.extend(["-p", p])
        for m in payload.mounts:
            cmd.extend(["-v", m])
        for e in payload.envs:
            cmd.extend(["-e", e])
        cmd.append(payload.image)
        run_subprocess(cmd)
        # Fetch fresh info about the new container
        container_list = [c for c in get_docker_containers() if c.name == payload.name]
        return container_list[0].dict() if container_list else {"detail": "created"}

    if typ == "lxc":
        if shutil.which("lxc") is None:
            raise HTTPException(status_code=404, detail="lxc not installed")
        try:
            run_subprocess(["lxc", "launch", payload.image, payload.name])
        except HTTPException as exc:
            if "Failed getting root disk" in str(exc.detail):
                raise HTTPException(
                    status_code=400,
                    detail="LXD storage not configured. Run 'lxd init' to set up a default storage pool.",
                ) from exc
            raise
        container_list = [c for c in get_lxc_containers() if c.name == payload.name]
        return container_list[0].dict() if container_list else {"detail": "created"}

    if typ == "kubernetes":
        if shutil.which("kubectl") is None:
            raise HTTPException(status_code=404, detail="kubectl not installed")
        run_subprocess(["kubectl", "run", payload.name, "--image", payload.image, "--restart=Never"])
        pods = [c for c in get_k8s_pods() if c.name == payload.name]
        return pods[0].dict() if pods else {"detail": "created"}

    # Fallback to in-memory creation for unknown types
    global next_container_id
    container = Container(
        id=next_container_id,
        name=payload.name,
        type=payload.type,
        status="running",
        image=payload.image,
        ports=payload.ports,
        mounts=payload.mounts,
        envs=payload.envs,
        cpu=payload.cpu,
        memory=payload.memory,
        created=datetime.utcnow().date().isoformat(),
    )
    next_container_id += 1
    containers.append(container)
    return container.dict()


@app.post("/containers/{name}/start")
def start_container(name: str):
    """Start a container by name if possible."""
    ctype = find_container_type(name)
    if ctype == "docker":
        if shutil.which("docker") is None:
            raise HTTPException(status_code=404, detail="docker not installed")
        result = subprocess.run(["docker", "start", name], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to start")
    elif ctype == "lxc":
        if shutil.which("lxc") is None:
            raise HTTPException(status_code=404, detail="lxc not installed")
        result = subprocess.run(["lxc", "start", name], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to start")
    elif ctype == "k8s":
        if shutil.which("kubectl") is None:
            raise HTTPException(status_code=404, detail="kubectl not installed")
        result = subprocess.run(["kubectl", "scale", "--replicas=1", f"deployment/{name}"], capture_output=True, text=True)
        if result.returncode != 0:
            result = subprocess.run(["kubectl", "scale", "--replicas=1", f"statefulset/{name}"], capture_output=True, text=True)
            if result.returncode != 0:
                raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to start")
    elif ctype == "api":
        for c in containers:
            if c.name == name:
                c.status = "running"
                break
    else:
        raise HTTPException(status_code=404, detail="container not found")
    return {"detail": "started"}


@app.post("/containers/{name}/stop")
def stop_container(name: str):
    """Stop a container by name if possible."""
    ctype = find_container_type(name)
    if ctype == "docker":
        if shutil.which("docker") is None:
            raise HTTPException(status_code=404, detail="docker not installed")
        result = subprocess.run(["docker", "stop", name], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to stop")
    elif ctype == "lxc":
        if shutil.which("lxc") is None:
            raise HTTPException(status_code=404, detail="lxc not installed")
        result = subprocess.run(["lxc", "stop", name], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to stop")
    elif ctype == "k8s":
        if shutil.which("kubectl") is None:
            raise HTTPException(status_code=404, detail="kubectl not installed")
        result = subprocess.run(["kubectl", "scale", "--replicas=0", f"deployment/{name}"], capture_output=True, text=True)
        if result.returncode != 0:
            result = subprocess.run(["kubectl", "scale", "--replicas=0", f"statefulset/{name}"], capture_output=True, text=True)
            if result.returncode != 0:
                raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to stop")
    elif ctype == "api":
        for c in containers:
            if c.name == name:
                c.status = "stopped"
                break
    else:
        raise HTTPException(status_code=404, detail="container not found")
    return {"detail": "stopped"}


@app.delete("/containers/{name}")
def delete_container(name: str):
    """Delete a container by name if possible."""
    ctype = find_container_type(name)
    if ctype == "docker":
        if shutil.which("docker") is None:
            raise HTTPException(status_code=404, detail="docker not installed")
        result = subprocess.run(["docker", "rm", name], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to delete")
    elif ctype == "lxc":
        if shutil.which("lxc") is None:
            raise HTTPException(status_code=404, detail="lxc not installed")
        result = subprocess.run(["lxc", "delete", "--force", name], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to delete")
    elif ctype == "k8s":
        if shutil.which("kubectl") is None:
            raise HTTPException(status_code=404, detail="kubectl not installed")
        result = subprocess.run(["kubectl", "delete", "pod", name], capture_output=True, text=True)
        if result.returncode != 0:
            result = subprocess.run(["kubectl", "delete", "deployment", name], capture_output=True, text=True)
            if result.returncode != 0:
                result = subprocess.run(["kubectl", "delete", "statefulset", name], capture_output=True, text=True)
                if result.returncode != 0:
                    raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to delete")
    elif ctype == "api":
        global containers
        containers = [c for c in containers if c.name != name]
    else:
        raise HTTPException(status_code=404, detail="container not found")
    return {"detail": "deleted"}


@app.websocket("/containers/{name}/terminal")
async def container_terminal(websocket: WebSocket, name: str):
    """Provide interactive shell access to a container via websocket."""
    await websocket.accept()
    ctype = find_container_type(name)
    if ctype == "docker":
        if shutil.which("docker") is None:
            await websocket.send_text("docker not installed")
            await websocket.close()
            return
        cmd = [
            "docker",
            "exec",
            "-it",
            name,
            "/bin/sh",
            "-c",
            "if [ -x /bin/bash ]; then exec /bin/bash -i; else exec /bin/sh -i; fi",
        ]
    elif ctype == "lxc":
        if shutil.which("lxc") is None:
            await websocket.send_text("lxc not installed")
            await websocket.close()
            return
        cmd = [
            "lxc",
            "exec",
            name,
            "--mode",
            "interactive",
            "--",
            "/bin/sh",
            "-c",
            "if [ -x /bin/bash ]; then exec /bin/bash -i; else exec /bin/sh -i; fi",
        ]
    elif ctype == "k8s":
        if shutil.which("kubectl") is None:
            await websocket.send_text("kubectl not installed")
            await websocket.close()
            return
        cmd = [
            "kubectl",
            "exec",
            "-it",
            name,
            "--",
            "/bin/sh",
            "-c",
            "if [ -x /bin/bash ]; then exec /bin/bash -i; else exec /bin/sh -i; fi",
        ]
    else:
        await websocket.close()
        return

    env = dict(os.environ)
    env["PS1"] = r"\\u@\\h:\\w$ "
    env["TERM"] = "xterm"

    master_fd, slave_fd = pty.openpty()
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        env=env,
        preexec_fn=os.setsid,
    )
    os.close(slave_fd)

    loop = asyncio.get_running_loop()

    async def read_output():
        try:
            while True:
                data = await loop.run_in_executor(None, os.read, master_fd, 1024)
                if not data:
                    break
                await websocket.send_text(data.decode(errors="ignore"))
        finally:
            os.close(master_fd)

    async def read_input():
        try:
            while True:
                data = await websocket.receive_text()
                os.write(master_fd, data.encode())

        except Exception:
            pass

    await asyncio.gather(read_output(), read_input())
    await websocket.close()


@app.get("/vms")
def list_vms():
    existing = load_vms()
    statuses = parse_virsh_list()
    for vm in existing:
        vm.status = statuses.get(vm.name, vm.status)
    for idx, vm in enumerate(existing, start=1):
        vm.id = idx
    return [vm.dict() for vm in existing]


@app.post("/vms")
def create_vm(payload: VirtualMachineCreate):
    if shutil.which("virt-install") is None:
        raise HTTPException(status_code=404, detail="virt-install not installed")
    iso_path = os.path.join(ISO_DIR, payload.iso)
    if not os.path.isfile(iso_path):
        raise HTTPException(status_code=404, detail="iso not found")

    disk_args = []
    disk_paths = []
    for idx, size in enumerate(payload.disks or [20], start=1):
        disk_path = f"/var/lib/libvirt/images/{payload.name}_{idx}.qcow2"
        disk_paths.append(disk_path)
        subprocess.run(["qemu-img", "create", "-f", "qcow2", disk_path, f"{size}G"], capture_output=True)
        disk_args.extend(["--disk", f"path={disk_path},size={size}"])

    cmd = [
        "virt-install",
        "--name",
        payload.name,
        "--ram",
        str(payload.memory),
        "--vcpus",
        str(payload.cpu),
        *disk_args,
        "--cdrom",
        iso_path,
        "--os-variant",
        "generic",
        "--network",
        "bridge=virbr0",
        "--graphics",
        "vnc",
        "--hvm",
        "--noautoconsole",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to create")

    vms = load_vms()
    vm = VirtualMachine(
        id=len(vms) + 1,
        name=payload.name,
        status="running",
        cpu=payload.cpu,
        memory=payload.memory,
        iso=payload.iso,
        disks=disk_paths,
        created=datetime.utcnow().date().isoformat(),
    )
    vms.append(vm)
    save_vms(vms)
    return vm.dict()


@app.patch("/vms/{name}")
def update_vm(name: str, payload: VirtualMachineUpdate):
    if shutil.which("virsh") is None:
        raise HTTPException(status_code=404, detail="virsh not installed")
    vms = load_vms()
    vm = next((v for v in vms if v.name == name), None)
    if not vm:
        raise HTTPException(status_code=404, detail="vm not found")
    if payload.cpu is not None:
        subprocess.run(["virsh", "setvcpus", name, str(payload.cpu), "--config"], capture_output=True)
        vm.cpu = payload.cpu
    if payload.memory is not None:
        subprocess.run(["virsh", "setmem", name, str(payload.memory * 1024), "--config"], capture_output=True)
        vm.memory = payload.memory
    if payload.iso is not None:
        iso_path = os.path.join(ISO_DIR, payload.iso)
        if not os.path.isfile(iso_path):
            raise HTTPException(status_code=404, detail="iso not found")
        subprocess.run([
            "virsh",
            "change-media",
            name,
            "--path",
            iso_path,
            "--device",
            "cdrom",
            "--config",
            "--update",
        ], capture_output=True)
        vm.iso = payload.iso
    if payload.add_disks:
        for size in payload.add_disks:
            idx = len(vm.disks) + 1
            disk_path = f"/var/lib/libvirt/images/{vm.name}_{idx}.qcow2"
            subprocess.run(["qemu-img", "create", "-f", "qcow2", disk_path, f"{size}G"], capture_output=True)
            subprocess.run(["virsh", "attach-disk", name, disk_path, f"vd{chr(96+idx)}", "--config"], capture_output=True)
            vm.disks.append(disk_path)
    save_vms(vms)
    return vm.dict()


@app.post("/vms/{name}/start")
def start_vm(name: str):
    if shutil.which("virsh") is None:
        raise HTTPException(status_code=404, detail="virsh not installed")
    result = subprocess.run(["virsh", "start", name], capture_output=True, text=True)
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to start")
    return {"detail": "started"}


@app.post("/vms/{name}/shutdown")
def shutdown_vm(name: str):
    if shutil.which("virsh") is None:
        raise HTTPException(status_code=404, detail="virsh not installed")
    result = subprocess.run(["virsh", "shutdown", name], capture_output=True, text=True)
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to shutdown")
    return {"detail": "shutting down"}


@app.delete("/vms/{name}")
def delete_vm(name: str):
    if shutil.which("virsh") is None:
        raise HTTPException(status_code=404, detail="virsh not installed")
    subprocess.run(["virsh", "destroy", name], capture_output=True)
    result = subprocess.run(["virsh", "undefine", name, "--remove-all-storage"], capture_output=True, text=True)
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to delete")
    vms = [vm for vm in load_vms() if vm.name != name]
    save_vms(vms)
    return {"detail": "deleted"}


@app.get("/metrics")
def metrics():
    return collect_metrics()


@app.get("/network/interfaces")
def list_network_interfaces():
    return {"interfaces": [i.dict() for i in get_network_interfaces()]}


@app.get("/network/settings")
def get_network_settings():
    return load_network_settings().dict()


@app.post("/network/settings")
def update_network_settings(payload: NetworkSettingsModel):
    save_network_settings(payload)
    return {"detail": "saved"}


@app.get("/drives")
def list_drives():
    return {"drives": [d.dict() for d in get_drives()]}





@app.get("/drives/zfs")
def list_zfs_pools():
    return {"pools": [p.dict() for p in get_zfs_pools()]}

@app.get("/drives/zfs-debug")
def zfs_debug():
    zpool_path = shutil.which("zpool")
    result = subprocess.run(["zpool", "status", "-P"], capture_output=True, text=True)
    return {
        "zpool_path": zpool_path,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr
    }

@app.post("/drives/mount")
def mount_drive(req: DriveMountRequest):
    if not os.path.exists(req.mountpoint):
        os.makedirs(req.mountpoint, exist_ok=True)
    result = subprocess.run(["mount", req.device, req.mountpoint], capture_output=True, text=True)
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to mount")
    return {"detail": "mounted"}


@app.post("/drives/format")
def format_drive(req: DriveFormatRequest):
    fs = req.filesystem.lower()
    if fs == "ext4":
        cmd = ["mkfs.ext4", "-F"]
    elif fs == "ntfs":
        cmd = ["mkfs.ntfs", "-F"]
    elif fs == "fat32":
        cmd = ["mkfs.vfat", "-F", "32"]
    elif fs == "exfat":
        cmd = ["mkfs.exfat"]
    elif fs == "zfs":
        if shutil.which("zpool") is None:
            raise HTTPException(status_code=404, detail="zfs not installed")
        pool = req.label or os.path.basename(req.device)
        cmd = ["zpool", "create", "-f", pool, req.device]
    else:
        raise HTTPException(status_code=400, detail="unsupported filesystem")
    if req.label and fs != "zfs":
        if fs in {"ext4", "ntfs"}:
            cmd.extend(["-L", req.label])
        else:
            cmd.extend(["-n", req.label])
    if fs != "zfs":
        cmd.append(req.device)
    # Unmount the device first in case it is currently mounted
    subprocess.run(["umount", req.device], capture_output=True)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to format")
    return {"detail": "formatted"}


@app.post("/drives/zfs")
def create_zfs_pool(req: ZFSPoolCreateRequest):
    if shutil.which("zpool") is None:
        raise HTTPException(status_code=404, detail="zfs not installed")
    if not req.devices:
        raise HTTPException(status_code=400, detail="no devices specified")
    cmd = ["zpool", "create", "-f", req.name]
    raid = req.raid.lower()
    if raid == "mirror":
        cmd.append("mirror")
    elif raid in {"raidz", "raidz2", "raidz3"}:
        cmd.append(raid)
    elif raid != "stripe":
        raise HTTPException(status_code=400, detail="invalid raid level")
    cmd.extend(req.devices)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to create pool")
    return {"detail": "created"}


@app.get("/users")
def api_list_users(limit: int = 20, offset: int = 0):
    """Return a paginated list of system users."""
    all_users = list_system_users()
    total = len(all_users)
    paginated = all_users[offset : offset + limit]
    return {"total": total, "users": [u.dict() for u in paginated]}


@app.post("/users")
def api_create_user(payload: UserCreateModel):
    cmd = ["useradd", "-m", "-s", payload.shell]
    if payload.groups:
        cmd.extend(["-G", ",".join(payload.groups)])
    cmd.append(payload.username)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to create")
    if payload.password:
        subprocess.run(["chpasswd"], input=f"{payload.username}:{payload.password}", text=True)
    return {"detail": "created"}


@app.put("/users/{username}")
def api_update_user(username: str, payload: UserUpdateModel):
    if payload.shell:
        result = subprocess.run(["usermod", "-s", payload.shell, username], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to modify")
    if payload.groups is not None:
        result = subprocess.run(["usermod", "-G", ",".join(payload.groups), username], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to modify")
    return {"detail": "updated"}


@app.delete("/users/{username}")
def api_delete_user(username: str):
    result = subprocess.run(["userdel", "-r", username], capture_output=True, text=True)
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to delete")
    return {"detail": "deleted"}





@app.get("/users/{username}/keys")
def api_get_user_keys(username: str):
    return {"keys": read_authorized_keys(username)}


@app.put("/users/{username}/keys")
def api_update_user_keys(username: str, payload: SSHKeyListModel):
    keys = [k.strip() for k in payload.keys if k.strip()]
    if len(keys) > 3:
        raise HTTPException(status_code=400, detail="maximum 3 keys allowed")
    write_authorized_keys(username, keys)
    return {"detail": "saved"}


@app.get("/groups")
def api_list_groups(limit: int = 20, offset: int = 0):
    """Return a paginated list of system groups."""
    all_groups = list_system_groups()
    total = len(all_groups)
    paginated = all_groups[offset : offset + limit]
    return {"total": total, "groups": [g.dict() for g in paginated]}


@app.post("/groups")
def api_create_group(payload: GroupCreateModel):
    result = subprocess.run(["groupadd", payload.name], capture_output=True, text=True)
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to create")
    if payload.members:
        subprocess.run(["gpasswd", "-M", ",".join(payload.members), payload.name], capture_output=True)
    return {"detail": "created"}


@app.put("/groups/{name}")
def api_update_group(name: str, payload: GroupUpdateModel):
    if payload.members is not None:
        result = subprocess.run(["gpasswd", "-M", ",".join(payload.members), name], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to modify")
    return {"detail": "updated"}


@app.delete("/groups/{name}")
def api_delete_group(name: str):
    result = subprocess.run(["groupdel", name], capture_output=True, text=True)
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to delete")
    return {"detail": "deleted"}


@app.get("/services")
def api_list_services():
    return {"services": list_systemd_services()}


@app.post("/services/{name}/start")
def api_start_service(name: str):
    if shutil.which("systemctl") is None:
        raise HTTPException(status_code=404, detail="systemctl not installed")
    result = subprocess.run(["systemctl", "start", name], capture_output=True, text=True)
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to start")
    return {"detail": "started"}


@app.post("/services/{name}/stop")
def api_stop_service(name: str):
    if shutil.which("systemctl") is None:
        raise HTTPException(status_code=404, detail="systemctl not installed")
    result = subprocess.run(["systemctl", "stop", name], capture_output=True, text=True)
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to stop")
    return {"detail": "stopped"}


@app.post("/services/{name}/enable")
def api_enable_service(name: str):
    if shutil.which("systemctl") is None:
        raise HTTPException(status_code=404, detail="systemctl not installed")
    result = subprocess.run(["systemctl", "enable", name], capture_output=True, text=True)
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to enable")
    return {"detail": "enabled"}


@app.post("/services/{name}/disable")
def api_disable_service(name: str):
    if shutil.which("systemctl") is None:
        raise HTTPException(status_code=404, detail="systemctl not installed")
    result = subprocess.run(["systemctl", "disable", name], capture_output=True, text=True)
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to disable")
    return {"detail": "disabled"}


LOG_DIR = "/var/log"


@app.get("/logs")
def api_list_logs():
    logs = []
    try:
        for name in os.listdir(LOG_DIR):
            path = os.path.join(LOG_DIR, name)
            if os.path.isfile(path):
                try:
                    size = os.path.getsize(path)
                except Exception:
                    size = 0
                logs.append({"name": name, "size": size})
    except Exception:
        pass
    return {"logs": logs}


@app.get("/logs/{name}")
def api_get_log(name: str, lines: int = 100):
    safe_name = os.path.basename(name)
    path = os.path.join(LOG_DIR, safe_name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="log not found")
    try:
        if lines > 0:
            result = run_subprocess(["tail", "-n", str(lines), path])
            content = result.stdout
        else:
            with open(path) as f:
                content = f.read()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="failed to read")
    return Response(content, media_type="text/plain")


@app.get("/settings")
def get_settings():
    return load_settings().dict()


@app.post("/settings")
def update_settings(payload: SettingsModel):
    save_settings(payload)
    try:
        with open("/etc/hosts", "r+") as f:
            lines = f.readlines()
            updated = False
            for i, line in enumerate(lines):
                if line.startswith("127.0.1.1"):
                    parts = line.split()
                    if len(parts) >= 1:
                        lines[i] = f"127.0.1.1\t{payload.hostname}\n"
                        updated = True
                        break
            if not updated:
                lines.append(f"127.0.1.1\t{payload.hostname}\n")
            f.seek(0)
            f.writelines(lines)
            f.truncate()
    except Exception:
        pass
    try:
        with open("/etc/hostname", "w") as f:
            f.write(payload.hostname.strip() + "\n")
        subprocess.run(["hostnamectl", "set-hostname", payload.hostname.strip()], capture_output=True)
    except Exception:
        pass
    try:
        config_path = "/etc/ssh/sshd_config"
        lines = []
        if os.path.exists(config_path):
            with open(config_path) as f:
                lines = f.readlines()
        found = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and stripped.lower().startswith("port"):
                lines[i] = f"Port {payload.ssh_port}\n"
                found = True
                break
        if not found:
            lines.append(f"Port {payload.ssh_port}\n")
        with open(config_path, "w") as f:
            f.writelines(lines)
        subprocess.run(["systemctl", "restart", "sshd"], capture_output=True)
    except Exception:
        pass
    return {"detail": "saved"}


@app.post("/settings/api-key")
def generate_api_key():
    settings = load_settings()
    settings.api_key = secrets.token_hex(16)
    save_settings(settings)
    return {"api_key": settings.api_key}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
