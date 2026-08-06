"""
System service management utilities using systemctl.
"""

import os
import subprocess
import shutil
import psutil
from typing import List
from lib.logger import log_service


def list_systemd_services() -> List[dict]:
    """Return a list of systemd services with status and enabled state."""
    services: List[dict] = []
    
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


def start_service(name: str) -> None:
    """Start a systemd service."""
    if shutil.which("systemctl") is None:
        raise Exception("systemctl not installed")
    
    result = subprocess.run(["systemctl", "start", name], capture_output=True, text=True)
    if result.returncode != 0:
        log_service(f"Failed to start service [{name}]: {result.stderr.strip()}", error=True)
        raise Exception(result.stderr.strip() or "failed to start")
    log_service(f"Started service [{name}]")


def stop_service(name: str) -> None:
    """Stop a systemd service."""
    if shutil.which("systemctl") is None:
        raise Exception("systemctl not installed")
    
    result = subprocess.run(["systemctl", "stop", name], capture_output=True, text=True)
    if result.returncode != 0:
        log_service(f"Failed to stop service [{name}]: {result.stderr.strip()}", error=True)
        raise Exception(result.stderr.strip() or "failed to stop")
    log_service(f"Stopped service [{name}]")


def enable_service(name: str) -> None:
    """Enable a systemd service to start at boot."""
    if shutil.which("systemctl") is None:
        raise Exception("systemctl not installed")
    
    result = subprocess.run(["systemctl", "enable", name], capture_output=True, text=True)
    if result.returncode != 0:
        log_service(f"Failed to enable service [{name}]: {result.stderr.strip()}", error=True)
        raise Exception(result.stderr.strip() or "failed to enable")
    log_service(f"Enabled service [{name}]")


def disable_service(name: str) -> None:
    """Disable a systemd service from starting at boot."""
    if shutil.which("systemctl") is None:
        raise Exception("systemctl not installed")
    
    result = subprocess.run(["systemctl", "disable", name], capture_output=True, text=True)
    if result.returncode != 0:
        log_service(f"Failed to disable service [{name}]: {result.stderr.strip()}", error=True)
        raise Exception(result.stderr.strip() or "failed to disable")
    log_service(f"Disabled service [{name}]")


def get_service_logs(name: str, lines: int = 100) -> List[dict]:
    """Get logs for a specific service."""
    logs = []
    
    if shutil.which("journalctl") is None:
        return logs
    
    try:
        cmd = ["journalctl", "-u", name]
        if lines > 0:
            cmd.extend(["-n", str(lines)])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.strip():
                    logs.append({"message": line, "timestamp": ""})
    except Exception:
        pass
    
    return logs