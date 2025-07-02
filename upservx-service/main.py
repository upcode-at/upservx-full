from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psutil
import platform
import subprocess
import json
import time
import os
import shutil
from datetime import datetime
from typing import List
from fastapi import HTTPException, WebSocket
import asyncio

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


class SettingsModel(BaseModel):
    hostname: str
    timezone: str
    auto_updates: bool
    monitoring: bool


SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")


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
        {"name": "Kubernetes", "service": "kubelet", "port": 6443},
        {"name": "LXC", "service": "lxc", "port": None},
        {"name": "SSH", "service": "ssh", "port": 22},
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
def list_images(type: str):
    """Return available container images for the given type."""
    type_lower = type.lower()
    if type_lower == "docker" or type_lower == "kubernetes":
        return {"images": get_docker_images()}
    if type_lower == "lxc":
        return {"images": get_lxc_images()}
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


@app.get("/settings")
def get_settings():
    return load_settings().dict()


@app.post("/settings")
def update_settings(payload: SettingsModel):
    save_settings(payload)
    return {"detail": "saved"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
