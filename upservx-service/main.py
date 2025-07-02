from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psutil
import platform
import subprocess
import time
import os
import shutil
from datetime import datetime
from typing import List

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
    cpu: float
    memory: int
    created: str


class ContainerCreate(BaseModel):
    name: str
    type: str
    image: str
    ports: List[str] = []
    mounts: List[str] = []
    cpu: float = 0.0
    memory: int = 0


containers: List[Container] = [
    Container(
        id=1,
        name="nginx-web",
        type="Docker",
        status="running",
        image="nginx:latest",
        ports=["80:8080", "443:8443"],
        mounts=["/data/web:/usr/share/nginx/html"],
        cpu=0.5,
        memory=128,
        created="2024-01-15",
    ),
    Container(
        id=2,
        name="mysql-db",
        type="Docker",
        status="running",
        image="mysql:8.0",
        ports=["3306:3306"],
        mounts=["/data/mysql:/var/lib/mysql"],
        cpu=1.2,
        memory=512,
        created="2024-01-14",
    ),
    Container(
        id=3,
        name="ubuntu-lxc",
        type="LXC",
        status="stopped",
        image="ubuntu:22.04",
        ports=[],
        mounts=["/data/ubuntu:/root"],
        cpu=0.0,
        memory=256,
        created="2024-01-10",
    ),
    Container(
        id=4,
        name="webapp-pod",
        type="Kubernetes",
        status="running",
        image="webapp:v1.2",
        ports=["8080:80"],
        mounts=["/data/app:/app/data"],
        cpu=0.8,
        memory=256,
        created="2024-01-12",
    ),
]

next_container_id = 5


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
    return [c.dict() for c in containers]


@app.post("/containers")
def create_container(payload: ContainerCreate):
    global next_container_id
    container = Container(
        id=next_container_id,
        name=payload.name,
        type=payload.type,
        status="running",
        image=payload.image,
        ports=payload.ports,
        mounts=payload.mounts,
        cpu=payload.cpu,
        memory=payload.memory,
        created=datetime.utcnow().date().isoformat(),
    )
    next_container_id += 1
    containers.append(container)
    return container.dict()


@app.get("/metrics")
def metrics():
    return collect_metrics()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
