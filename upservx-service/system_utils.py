"""
System information utilities for the UpservX API.
"""

import platform
import subprocess
import psutil
import time
import shutil
import os
import socket


# Track last network counters for throughput calculation
_prev_net_io = psutil.net_io_counters()
_prev_net_time = time.time()


def format_uptime(seconds: float) -> str:
    """Format uptime seconds into a human-readable string."""
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
    """Return the CPU model name."""
    model = platform.processor()
    if not model:
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name"):
                        return line.split(":", 1)[1].strip()
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


def collect_metrics() -> dict:
    """Collect system metrics including CPU, memory, disk, network, and GPU information."""
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
                    try:
                        return int(line.split()[1])
                    except (IndexError, ValueError):
                        pass
    except Exception:
        pass
    return 22


def _system_nameservers() -> tuple[str, str]:
    """Return primary and secondary nameservers from /etc/resolv.conf."""
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


def get_server_addresses() -> list[str]:
    """Get all IP addresses and hostnames of the server for CORS configuration.
    
    Returns a list of origins including:
    - All network interface IPs with common ports (3000, 8000, 80, 443, 5173)
    - Hostname with common ports
    - localhost and 127.0.0.1 for development
    """
    origins = []
    ports = [3000, 8000, 80, 443, 5173, 3001]
    protocols = ["http", "https"]
    
    # Add localhost
    for protocol in protocols:
        for port in ports:
            origins.append(f"{protocol}://localhost:{port}")
            origins.append(f"{protocol}://127.0.0.1:{port}")
        # Add without port for standard ports
        origins.append(f"{protocol}://localhost")
        origins.append(f"{protocol}://127.0.0.1")
    
    # Add hostname
    try:
        hostname = socket.gethostname()
        for protocol in protocols:
            for port in ports:
                origins.append(f"{protocol}://{hostname}:{port}")
            # Add without port for standard ports
            origins.append(f"{protocol}://{hostname}")
    except Exception:
        pass
    
    # Add all network interface IPs
    try:
        addrs = psutil.net_if_addrs()
        for interface, addr_list in addrs.items():
            for addr in addr_list:
                if addr.family == socket.AF_INET:  # IPv4
                    ip = addr.address
                    if ip and ip != "127.0.0.1":
                        for protocol in protocols:
                            for port in ports:
                                origins.append(f"{protocol}://{ip}:{port}")
                            # Add without port for standard ports
                            origins.append(f"{protocol}://{ip}")
    except Exception:
        pass
    
    return origins