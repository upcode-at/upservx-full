"""
Settings and configuration management utilities.
"""

import os
import json
import subprocess
import secrets
import platform
from lib.models import SettingsModel

SETTINGS_FILE = "/etc/upservx/settings.json"
os.makedirs("/etc/upservx", exist_ok=True)
VPN_DIR = os.path.join(os.path.dirname(__file__), "vpn")
VPN_PIDFILE = "/var/run/upservx_vpn.pid"
VPN_OVPN_NAME = "client.ovpn"

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
        deny_root_login=data.get("deny_root_login", False),
        api_key=data.get("api_key"),
    )

def save_settings(settings: SettingsModel) -> None:
    """Save settings to file."""
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings.dict(), f)

def apply_system_settings(settings: SettingsModel) -> None:
    """Apply settings to the actual system configuration."""
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
    
    try:
        with open("/etc/hostname", "w") as f:
            f.write(settings.hostname.strip() + "\n")
        subprocess.run(["hostnamectl", "set-hostname", settings.hostname.strip()], capture_output=True)
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

def save_vpn_ovpn(content: bytes, filename: str | None = None) -> str:
    """Save uploaded .ovpn content to the VPN directory and return path."""
    os.makedirs(VPN_DIR, exist_ok=True)
    name = filename or VPN_OVPN_NAME
    safe_name = os.path.basename(name)
    path = os.path.join(VPN_DIR, safe_name)

    with open(path, "wb") as f:
        f.write(content)

    try:
        os.chmod(path, 0o600)
    except Exception:
        pass

    return path

def _read_pidfile() -> int | None:
    try:
        if os.path.exists(VPN_PIDFILE):
            with open(VPN_PIDFILE) as f:
                pid = int(f.read().strip())
                return pid
    except Exception:
        pass
    return None

def get_vpn_status() -> dict:
    """Return VPN status dict: {'running': bool, 'pid': int|None, 'ovpn_path': str|None}"""
    pid = _read_pidfile()
    running = False
    if pid:
        try:
            os.kill(pid, 0)
            running = True
        except Exception:
            running = False

    ovpn_path = None
    # Prefer the default name, otherwise pick the first .ovpn in the directory
    candidate = os.path.join(VPN_DIR, VPN_OVPN_NAME)
    if os.path.exists(candidate):
        ovpn_path = candidate
    else:
        try:
            for f in os.listdir(VPN_DIR):
                if f.lower().endswith('.ovpn'):
                    ovpn_path = os.path.join(VPN_DIR, f)
                    break
        except Exception:
            ovpn_path = None

    return {"running": running, "pid": pid, "ovpn_path": ovpn_path}

def start_vpn() -> dict:
    """Start OpenVPN using the saved .ovpn file. Returns status dict."""
    # Pick the configured default file, otherwise any .ovpn in the VPN_DIR
    ovpn = os.path.join(VPN_DIR, VPN_OVPN_NAME)
    if not os.path.exists(ovpn):
        try:
            # find any .ovpn
            found = None
            for f in os.listdir(VPN_DIR):
                if f.lower().endswith('.ovpn'):
                    found = os.path.join(VPN_DIR, f)
                    break
            if found:
                ovpn = found
            else:
                raise Exception("ovpn file not found")
        except FileNotFoundError:
            raise Exception("ovpn file not found")

    # If already running, return status
    status = get_vpn_status()
    if status.get("running"):
        return status

    # Try to start openvpn as daemon and write pidfile
    cmd = ["openvpn", "--config", ovpn, "--writepid", VPN_PIDFILE, "--daemon"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise Exception(res.stderr or "failed to start openvpn")

        return get_vpn_status()
    except FileNotFoundError:
        raise Exception("openvpn binary not found on system")
    except Exception as e:
        raise

def stop_vpn() -> dict:
    """Stop running OpenVPN process started by this service."""
    pid = _read_pidfile()
    if not pid:
        return get_vpn_status()

    try:
        os.kill(pid, 15)
    except ProcessLookupError:
        pass
    except Exception:
        pass

    try:
        if os.path.exists(VPN_PIDFILE):
            os.remove(VPN_PIDFILE)
    except Exception:
        pass

    return get_vpn_status()