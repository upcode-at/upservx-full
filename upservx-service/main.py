from fastapi import FastAPI, HTTPException, WebSocket, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
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
from typing import List
import asyncio
import socket

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")
NETWORK_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "network_settings.json")
ISO_DIR = os.path.join(os.path.dirname(__file__), "isos")
os.makedirs(ISO_DIR, exist_ok=True)


def load_settings() -> SettingsModel:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                data = json.load(f)
                return SettingsModel(**data)
        except Exception:
            pass
    return SettingsModel(
        hostname=platform.node() or "server",
        timezone="utc",
        auto_updates=False,
        monitoring=True,
    )


def save_settings(settings: SettingsModel) -> None:
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings.dict(), f)


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
        json.dump(settings.dict(), f)


# Containers that are created via the API are stored here in-memory. Containers
# discovered from Docker, LXC or Kubernetes are queried on demand and not stored
# in this list.
containers: List[Container] = []

next_container_id = 1


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
    try:
        output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        return output.splitlines()[0] if output else "none"
    except Exception:
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
        {"name": "SSH", "service": "sshd", "port": 22},
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
        return container_list[0].dict() if container_list else {"detail": "created"}

    if typ == "lxc":
        if shutil.which("lxc") is None:
            raise HTTPException(status_code=404, detail="lxc not installed")
        result = subprocess.run(["lxc", "launch", payload.image, payload.name], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to create")
        container_list = [c for c in get_lxc_containers() if c.name == payload.name]
        return container_list[0].dict() if container_list else {"detail": "created"}

    if typ == "kubernetes":
        if shutil.which("kubectl") is None:
            raise HTTPException(status_code=404, detail="kubectl not installed")
        result = subprocess.run(["kubectl", "run", payload.name, "--image", payload.image, "--restart=Never"], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to create")
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
    return {"detail": "saved"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
