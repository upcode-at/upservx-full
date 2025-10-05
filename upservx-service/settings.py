"""
Settings and configuration management utilities.
"""

import os
import json
import subprocess
import secrets
import platform
from models import SettingsModel


SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")


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


def load_settings() -> SettingsModel:
    """Load settings from file or system defaults."""
    data: dict = {}
    
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
        api_key=data.get("api_key"),
    )


def save_settings(settings: SettingsModel) -> None:
    """Save settings to file."""
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings.dict(), f)


def apply_system_settings(settings: SettingsModel) -> None:
    """Apply settings to the actual system configuration."""
    # Update /etc/hosts
    try:
        with open("/etc/hosts", "r+") as f:
            lines = f.readlines()
            f.seek(0)
            for line in lines:
                if line.startswith("127.0.1.1"):
                    f.write(f"127.0.1.1\t{settings.hostname.strip()}\n")
                else:
                    f.write(line)
            f.truncate()
    except Exception:
        pass
    
    # Update hostname
    try:
        with open("/etc/hostname", "w") as f:
            f.write(settings.hostname.strip() + "\n")
        subprocess.run(["hostnamectl", "set-hostname", settings.hostname.strip()], capture_output=True)
    except Exception:
        pass
    
    # Update SSH port
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
                lines[i] = f"Port {settings.ssh_port}\n"
                found = True
                break
        
        if not found:
            lines.append(f"Port {settings.ssh_port}\n")
        
        with open(config_path, "w") as f:
            f.writelines(lines)
        
        subprocess.run(["systemctl", "restart", "sshd"], capture_output=True)
    except Exception:
        pass


def generate_api_key() -> str:
    """Generate a new API key and save it to settings."""
    settings = load_settings()
    settings.api_key = secrets.token_hex(16)
    save_settings(settings)
    return settings.api_key


def get_log_files() -> list:
    """Get a list of available log files."""
    logs = []
    log_dir = "/var/log"
    
    try:
        for name in os.listdir(log_dir):
            path = os.path.join(log_dir, name)
            if os.path.isfile(path):
                try:
                    stat = os.stat(path)
                    logs.append({
                        "name": name,
                        "size": stat.st_size,
                        "path": path,
                    })
                except Exception:
                    pass
    except Exception:
        pass
    
    return logs


def read_log_file(name: str, lines: int = 100) -> str:
    """Read content from a log file."""
    log_dir = "/var/log"
    safe_name = os.path.basename(name)
    path = os.path.join(log_dir, safe_name)
    
    if not os.path.isfile(path):
        raise Exception("log not found")
    
    try:
        if lines > 0:
            result = subprocess.run(["tail", "-n", str(lines), path], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout
        else:
            with open(path) as f:
                return f.read()
    except Exception as e:
        raise Exception(f"failed to read: {str(e)}")
    
    return ""