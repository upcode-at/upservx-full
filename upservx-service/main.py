from fastapi import FastAPI, HTTPException, WebSocket, UploadFile, File, Request
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import base64
import pam
from pydantic import BaseModel
import psutil
import platform
import subprocess
import json
import time
import os
import shutil
import urllib.request
import urllib.parse
from datetime import datetime
from typing import List, Any
import pwd
import grp
import asyncio
import socket
import logging

app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("upservx-service")

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
        if scheme.lower() != "basic":
            raise ValueError
        decoded = base64.b64decode(credentials).decode()
        username, password = decoded.split(":", 1)
    except Exception:
        return Response(status_code=401, headers={"WWW-Authenticate": "Basic"})
    if not pam_auth.authenticate(username, password):
        return Response(status_code=401, headers={"WWW-Authenticate": "Basic"})
    request.state.user = username
    response = await call_next(request)
    return response


@app.get("/")
def read_root():
    return {"detail": "ok"}


class Container(BaseModel):
    id: int
    name: str
    type: str
    status: str
    image: str
    ports: List[str] = []
    mounts: List[str] = []
    envs: List[str] = []
    cpu: float
    memory: int
    created: str


class ContainerCreate(BaseModel):
    name: str
    type: str
    image: str
    ports: List[str] = []
    mounts: List[str] = []
    envs: List[str] = []
    cpu: float = 0.0
    memory: int = 0


class ISOInfo(BaseModel):
    id: int
    name: str
    size: float
    type: str
    version: str
    architecture: str
    created: str
    used: bool
    path: str


class ContainerImageInfo(BaseModel):
    id: int
    repository: str
    tag: str
    imageId: str
    size: float
    created: str
    used: bool = False
    pulls: int = 0


class VM(BaseModel):
    id: int
    name: str
    os: str
    status: str
    cpu: int
    memory: int
    disks: List[int]
    ip: str


class VMCreate(BaseModel):
    name: str
    os: str
    cpu: int
    memory: int
    disks: List[int]


class DriveInfo(BaseModel):
    device: str
    name: str
    type: str
    size: float
    used: float
    available: float
    filesystem: str
    mountpoint: str
    mounted: bool
    health: str = "good"
    temperature: int | None = None


class NetworkInterfaceInfo(BaseModel):
    name: str
    type: str
    status: str
    ip: str
    netmask: str
    gateway: str
    mac: str
    speed: str
    rx: str
    tx: str


class NetworkSettingsModel(BaseModel):
    dns_primary: str = "8.8.8.8"
    dns_secondary: str = "8.8.4.4"


class SettingsModel(BaseModel):
    hostname: str
    timezone: str
    auto_updates: bool
    monitoring: bool
    ssh_port: int = 22


SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")
NETWORK_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "network_settings.json")
DEFAULT_VM_BASE = "/var/lib/libvirt/images"
FALLBACK_VM_BASE = os.path.join(os.path.dirname(__file__), "images")


def _init_vm_dirs(base: str) -> tuple[str, str, str]:
    iso_dir = os.path.join(base, "isos")
    vm_dir = os.path.join(base, "vms")
    os.makedirs(iso_dir, exist_ok=True)
    os.makedirs(vm_dir, exist_ok=True)
    return base, iso_dir, vm_dir


try:
    DEFAULT_VM_BASE, ISO_DIR, VM_DIR = _init_vm_dirs(DEFAULT_VM_BASE)
except PermissionError:
    logger.warning(
        "Fallback to %s for VM storage due to permission issues", FALLBACK_VM_BASE
    )
    DEFAULT_VM_BASE, ISO_DIR, VM_DIR = _init_vm_dirs(FALLBACK_VM_BASE)


def _system_hostname() -> str:
    """Return the system hostname from /etc/hostname or platform.node()."""
    try:
        with open("/etc/hostname") as f:
            hostname = f.read().strip()
            if hostname:
                return hostname
    except Exception:
        pass
    return platform.node() or "server"


def _system_ssh_port() -> int:
    """Return the SSH port from /etc/ssh/sshd_config or 22."""
    try:
        with open("/etc/ssh/sshd_config") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and line.lower().startswith("port"):
                    parts = line.split()
                    if len(parts) > 1 and parts[1].isdigit():
                        return int(parts[1])
    except Exception:
        pass
    return 22


def load_settings() -> SettingsModel:
    data: dict[str, Any] = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                data = json.load(f)
        except Exception:
            data = {}
    return SettingsModel(
        hostname=_system_hostname(),
        timezone=data.get("timezone", "utc"),
        auto_updates=data.get("auto_updates", False),
        monitoring=data.get("monitoring", True),
        ssh_port=data.get("ssh_port", _system_ssh_port()),
    )


def save_settings(settings: SettingsModel) -> None:
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings.model_dump(), f)


def _system_nameservers() -> tuple[str, str]:
    primary = "8.8.8.8"
    secondary = "8.8.4.4"
    try:
        with open("/etc/resolv.conf") as f:
            nameservers = [
                line.split()[1]
                for line in f
                if line.strip().startswith("nameserver") and len(line.split()) >= 2
            ]
        if nameservers:
            primary = nameservers[0]
            if len(nameservers) > 1:
                secondary = nameservers[1]
    except Exception:
        pass
    return primary, secondary


def load_network_settings() -> NetworkSettingsModel:
    if os.path.exists(NETWORK_SETTINGS_FILE):
        try:
            with open(NETWORK_SETTINGS_FILE) as f:
                data = json.load(f)
                primary, secondary = _system_nameservers()
                return NetworkSettingsModel(
                    dns_primary=data.get("dns_primary", primary),
                    dns_secondary=data.get("dns_secondary", secondary),
                )
        except Exception:
            pass
    primary, secondary = _system_nameservers()
    return NetworkSettingsModel(dns_primary=primary, dns_secondary=secondary)


def save_network_settings(settings: NetworkSettingsModel) -> None:
    with open(NETWORK_SETTINGS_FILE, "w") as f:
        json.dump(settings.model_dump(), f)


LOGIN_SHELLS = {
    "/bin/bash",
    "/bin/sh",
    "/bin/fish",
    "/bin/zsh",
    "/usr/bin/bash",
    "/usr/bin/sh",
    "/usr/bin/fish",
    "/usr/bin/zsh",
}


class SystemUserModel(BaseModel):
    username: str
    uid: int
    gid: int
    groups: List[str]
    shell: str
    home: str
    description: str | None = ""


class SystemGroupModel(BaseModel):
    name: str
    gid: int
    members: List[str]
    description: str | None = ""


def list_system_users() -> List[SystemUserModel]:
    users: List[SystemUserModel] = []
    all_groups = grp.getgrall()
    for entry in pwd.getpwall():
        if entry.pw_shell not in LOGIN_SHELLS:
            continue
        groups = [g.gr_name for g in all_groups if entry.pw_name in g.gr_mem or g.gr_gid == entry.pw_gid]
        users.append(
            SystemUserModel(
                username=entry.pw_name,
                uid=entry.pw_uid,
                gid=entry.pw_gid,
                groups=groups,
                shell=entry.pw_shell,
                home=entry.pw_dir,
                description=entry.pw_gecos.split(',')[0] if entry.pw_gecos else "",
            )
        )
    return users


def list_system_groups() -> List[SystemGroupModel]:
    groups: List[SystemGroupModel] = []
    for entry in grp.getgrall():
        groups.append(
            SystemGroupModel(
                name=entry.gr_name,
                gid=entry.gr_gid,
                members=list(entry.gr_mem),
            )
        )
    return groups


class UserCreateModel(BaseModel):
    username: str
    password: str
    groups: List[str] = []
    shell: str = "/bin/bash"


class UserUpdateModel(BaseModel):
    groups: List[str] | None = None
    shell: str | None = None


class GroupCreateModel(BaseModel):
    name: str
    members: List[str] = []


class GroupUpdateModel(BaseModel):
    members: List[str] | None = None


class SSHKeyListModel(BaseModel):
    keys: List[str] = []


# Containers that are created via the API are stored here in-memory. Containers
# discovered from Docker, LXC or Kubernetes are queried on demand and not stored
# in this list.
containers: List[Container] = []

next_container_id = 1

# Virtual machines created via the API are stored here in-memory.
# Disk and ISO images are placed under /var/lib/libvirt/images so the hypervisor
# can access them without permission issues.

vms: List[VM] = []
next_vm_id = 1
vm_disks: dict[str, List[str]] = {}


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


def _parse_ports(port_str: str) -> List[str]:
    """Split Docker style port mappings into a list."""
    if not port_str:
        return []
    return [p.strip() for p in port_str.split(',') if p.strip()]


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
                ports=_parse_ports(ports),
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
        containers_list.append(
            Container(
                id=0,
                name=item.get("name", ""),
                type="LXC",
                status=item.get("status", "").lower(),
                image=item.get("config", {}).get("image.os", ""),
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


def _parse_docker_size(size: str) -> float:
    size = size.lower().strip()
    if size.endswith("gb"):
        try:
            return float(size[:-2].strip()) * 1000
        except ValueError:
            return 0.0
    if size.endswith("mb"):
        try:
            return float(size[:-2].strip())
        except ValueError:
            return 0.0
    return 0.0


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
                size=_parse_docker_size(size),
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
        repository, _, tag = alias.partition(":")
        images.append(
            ContainerImageInfo(
                id=idx,
                repository=repository or alias,
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


def guess_iso_info(filename: str) -> tuple[str, str, str]:
    lower = filename.lower()
    typ = "Windows" if "win" in lower or "windows" in lower else "Linux"
    arch = "arm64" if "arm64" in lower or "aarch64" in lower else "x86_64"
    version = filename.rsplit(".", 1)[0]
    return typ, version, arch


def get_iso_files() -> List[ISOInfo]:
    files: List[ISOInfo] = []
    if not os.path.isdir(ISO_DIR):
        return files
    for idx, name in enumerate(sorted(os.listdir(ISO_DIR)), start=1):
        if not name.lower().endswith(".iso"):
            continue
        path = os.path.join(ISO_DIR, name)
        try:
            stat = os.stat(path)
        except FileNotFoundError:
            continue
        size = round(stat.st_size / (1024 ** 3), 1)
        created = datetime.fromtimestamp(stat.st_mtime).date().isoformat()
        typ, version, arch = guess_iso_info(name)
        files.append(
            ISOInfo(
                id=idx,
                name=name,
                size=size,
                type=typ,
                version=version,
                architecture=arch,
                created=created,
                used=False,
                path=path,
            )
        )
    return files


def _drive_type(dev: str) -> str:
    """Return the type for a device or partition."""
    name = os.path.basename(dev)
    # Resolve base device if this is a partition
    try:
        base = os.path.basename(os.path.realpath(os.path.join("/sys/class/block", name, "..")))
    except Exception:
        base = name
    rotational = f"/sys/block/{base}/queue/rotational"
    removable = f"/sys/block/{base}/removable"
    try:
        with open(removable) as f:
            if f.read().strip() == "1":
                return "USB"
    except Exception:
        pass
    try:
        with open(rotational) as f:
            if f.read().strip() == "0":
                return "SSD"
    except Exception:
        pass
    if name.startswith("mmc"):
        return "SD"
    return "HDD"


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
                type=_drive_type(dev),
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
    net = psutil.net_io_counters()
    uptime_seconds = time.time() - psutil.boot_time()

    services_info = [
        {"name": "Docker", "service": "docker", "port": 2376},
        {"name": "Kubernetes", "service": "k3s", "port": 6443},
        {"name": "LXC", "service": "lxd", "port": None},
        {"name": "SSH", "service": "sshd", "port": _system_ssh_port()},
        {"name": "Web Interface", "service": "nginx", "port": 8080},
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
            "in": round(net.bytes_recv / (1024 ** 2), 2),
            "out": round(net.bytes_sent / (1024 ** 2), 2),
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
    return [c.model_dump() for c in all_containers]


@app.get("/images")
def list_images(type: str, full: bool = False):
    """Return available container images for the given type."""
    type_lower = type.lower()
    if full:
        if type_lower in {"docker", "kubernetes"}:
            return {"images": [img.model_dump() for img in get_docker_image_details()]}
        if type_lower == "lxc":
            return {"images": [img.model_dump() for img in get_lxc_image_details()]}
    else:
        if type_lower in {"docker", "kubernetes"}:
            return {"images": get_docker_images()}
        if type_lower == "lxc":
            return {"images": get_lxc_images()}
    raise HTTPException(status_code=400, detail="unknown container type")


@app.get("/isos")
def list_isos():
    return {"isos": [iso.model_dump() for iso in get_iso_files()]}


class ISODownloadRequest(BaseModel):
    url: str
    name: str | None = None


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
    return info.model_dump()


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
    return info.model_dump()


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


class ImagePullRequest(BaseModel):
    image: str
    registry: str | None = None
    type: str = "docker"


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
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to create")
        # Fetch fresh info about the new container
        container_list = [c for c in get_docker_containers() if c.name == payload.name]
        return container_list[0].model_dump() if container_list else {"detail": "created"}

    if typ == "lxc":
        if shutil.which("lxc") is None:
            raise HTTPException(status_code=404, detail="lxc not installed")
        result = subprocess.run(["lxc", "launch", payload.image, payload.name], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to create")

    if typ == "kubernetes":
        if shutil.which("kubectl") is None:
            raise HTTPException(status_code=404, detail="kubectl not installed")
        result = subprocess.run(["kubectl", "run", payload.name, "--image", payload.image, "--restart=Never"], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to create")
        pods = [c for c in get_k8s_pods() if c.name == payload.name]
        return pods[0].model_dump() if pods else {"detail": "created"}

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
    return container.model_dump()


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
        cmd = ["docker", "exec", "-i", name, "/bin/sh"]
    elif ctype == "lxc":
        if shutil.which("lxc") is None:
            await websocket.send_text("lxc not installed")
            await websocket.close()
            return
        cmd = ["lxc", "exec", name, "--", "/bin/sh"]
    elif ctype == "k8s":
        if shutil.which("kubectl") is None:
            await websocket.send_text("kubectl not installed")
            await websocket.close()
            return
        cmd = ["kubectl", "exec", "-i", name, "--", "/bin/sh"]
    else:
        await websocket.close()
        return

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    async def read_output():
        try:
            while True:
                data = await process.stdout.readline()
                if not data:
                    break
                await websocket.send_text(data.decode())
        finally:
            await websocket.close()

    async def read_input():
        try:
            while True:
                text = await websocket.receive_text()
                if process.stdin:
                    process.stdin.write(text.encode())
                    process.stdin.write(b"\n")
                    await process.stdin.drain()
        except Exception:
            pass

    await asyncio.gather(read_output(), read_input())


@app.get("/vms")
def list_vms():
    logger.info("Listing VMs")
    return [vm.model_dump() for vm in vms]


@app.post("/vms")
def create_vm(payload: VMCreate):
    global next_vm_id
    logger.info("Creating VM %s", payload.name)
    vm_dir = os.path.join(VM_DIR, payload.name)
    os.makedirs(vm_dir, exist_ok=True)
    disk_files: List[str] = []
    for idx, size in enumerate(payload.disks, start=1):
        disk_path = os.path.join(vm_dir, f"disk{idx}.qcow2")
        try:
            subprocess.run(
                ["qemu-img", "create", "-f", "qcow2", disk_path, f"{size}G"],
                check=True,
            )
            logger.info("Created disk %s of size %sG for VM %s", disk_path, size, payload.name)
        except subprocess.CalledProcessError as e:
            raise HTTPException(status_code=400, detail=str(e))
        disk_files.append(disk_path)

    vm = VM(
        id=next_vm_id,
        name=payload.name,
        os=payload.os,
        status="stopped",
        cpu=payload.cpu,
        memory=payload.memory,
        disks=payload.disks,
        ip=f"192.168.122.{100 + next_vm_id}",
    )
    next_vm_id += 1
    vms.append(vm)
    vm_disks[payload.name] = disk_files
    logger.info("VM %s created with ID %s", payload.name, vm.id)
    return vm.model_dump()


@app.post("/vms/{name}/start")
def start_vm(name: str):
    for vm in vms:
        if vm.name == name:
            if vm.status == "running":
                raise HTTPException(status_code=400, detail="vm already running")
            logger.info("Starting VM %s", name)
            iso_path = os.path.join(ISO_DIR, vm.os)
            disk_files = vm_disks.get(name, [])
            cmd = [
                "sudo",
                "virt-install",
                "--name",
                name,
                "--ram",
                str(vm.memory),
                "--vcpus",
                str(vm.cpu),
                "--network",
                "bridge=virbr0",
                "--graphics",
                "none",
                "--hvm",
                "--noautoconsole",
                "--wait",
                "0",
                "--osinfo",
                "detect=on,require=off",
            ]
            if os.path.isfile(iso_path):
                cmd.extend(["--cdrom", iso_path])
            for disk in disk_files:
                cmd.extend(["--disk", f"path={disk}"])
            try:
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError as e:
                raise HTTPException(status_code=400, detail=e.stderr or str(e))
            vm.status = "running"
            logger.info("VM %s started", name)
            return {"detail": "started"}
    raise HTTPException(status_code=404, detail="vm not found")


@app.post("/vms/{name}/stop")
def stop_vm(name: str):
    for vm in vms:
        if vm.name == name:
            logger.info("Stopping VM %s", name)
            try:
                subprocess.run(["sudo", "virsh", "destroy", name], check=True)
            except subprocess.CalledProcessError as e:
                raise HTTPException(status_code=400, detail=e.stderr or str(e))
            vm.status = "stopped"
            logger.info("VM %s stopped", name)
            return {"detail": "stopped"}
    raise HTTPException(status_code=404, detail="vm not found")


@app.delete("/vms/{name}")
def delete_vm(name: str):
    global vms
    for vm in vms:
        if vm.name == name:
            logger.info("Deleting VM %s", name)
            try:
                subprocess.run(["sudo", "virsh", "undefine", name], check=True)
            except subprocess.CalledProcessError:
                pass
            vm_dir = os.path.join(VM_DIR, name)
            shutil.rmtree(vm_dir, ignore_errors=True)
            vm_disks.pop(name, None)
            vms = [v for v in vms if v.name != name]
            logger.info("VM %s deleted", name)
            return {"detail": "deleted"}
    raise HTTPException(status_code=404, detail="vm not found")


@app.get("/metrics")
def metrics():
    return collect_metrics()


@app.get("/network/interfaces")
def list_network_interfaces():
    return {"interfaces": [i.model_dump() for i in get_network_interfaces()]}


@app.get("/network/settings")
def get_network_settings():
    return load_network_settings().model_dump()


@app.post("/network/settings")
def update_network_settings(payload: NetworkSettingsModel):
    save_network_settings(payload)
    return {"detail": "saved"}


@app.get("/drives")
def list_drives():
    return {"drives": [d.model_dump() for d in get_drives()]}


class DriveMountRequest(BaseModel):
    device: str
    mountpoint: str


class DriveFormatRequest(BaseModel):
    device: str
    filesystem: str
    label: str | None = None


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
    else:
        raise HTTPException(status_code=400, detail="unsupported filesystem")
    if req.label:
        if fs in {"ext4", "ntfs"}:
            cmd.extend(["-L", req.label])
        else:
            cmd.extend(["-n", req.label])
    cmd.append(req.device)
    # Unmount the device first in case it is currently mounted
    subprocess.run(["umount", req.device], capture_output=True)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to format")
    return {"detail": "formatted"}


@app.get("/users")
def api_list_users(limit: int = 20, offset: int = 0):
    """Return a paginated list of system users."""
    all_users = list_system_users()
    total = len(all_users)
    paginated = all_users[offset : offset + limit]
    return {"total": total, "users": [u.model_dump() for u in paginated]}


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


def _authorized_keys_path(username: str) -> str:
    info = pwd.getpwnam(username)
    return os.path.join(info.pw_dir, ".ssh", "authorized_keys")


def read_authorized_keys(username: str) -> List[str]:
    path = _authorized_keys_path(username)
    if os.path.exists(path):
        try:
            with open(path) as f:
                return [line.strip() for line in f if line.strip()]
        except Exception:
            return []
    return []


def write_authorized_keys(username: str, keys: List[str]) -> None:
    info = pwd.getpwnam(username)
    ssh_dir = os.path.join(info.pw_dir, ".ssh")
    os.makedirs(ssh_dir, exist_ok=True)
    path = os.path.join(ssh_dir, "authorized_keys")
    with open(path, "w") as f:
        for key in keys:
            if key.strip():
                f.write(key.strip() + "\n")
    try:
        os.chown(ssh_dir, info.pw_uid, info.pw_gid)
        os.chmod(ssh_dir, 0o700)
        os.chown(path, info.pw_uid, info.pw_gid)
        os.chmod(path, 0o600)
    except Exception:
        pass


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
    return {"total": total, "groups": [g.model_dump() for g in paginated]}


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


@app.get("/settings")
def get_settings():
    return load_settings().model_dump()


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
