"""
Settings and configuration management utilities.
"""

import os
import json
import subprocess
import platform
from lib.models import SettingsModel
from lib.secure_store import ensure_config_directory, secure_write_json, secure_write_bytes
from lib.privileged import require_privileged, require_privileged_json

SETTINGS_FILE = "/etc/upservx/settings.json"
LOG_DIR = "/var/log"
MAX_LOG_SCAN_DEPTH = 1
VPN_DIR = "/etc/upservx/vpn"
VPN_PIDFILE = "/run/upservx/openvpn.pid"
VPN_OVPN_NAME = "client.ovpn"

def _ensure_vpn_dir() -> None:
    """Ensure VPN_DIR exists."""
    ensure_config_directory(VPN_DIR)

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
        timezone=data.get("timezone", "UTC"),
        auto_updates=data.get("auto_updates", False),
        monitoring=data.get("monitoring", True),
        ssh_port=data.get("ssh_port", _system_ssh_port()),
        deny_root_login=data.get("deny_root_login", False),
    )

def save_settings(settings: SettingsModel) -> None:
    """Save settings to file."""
    secure_write_json(SETTINGS_FILE, settings.model_dump())

def apply_system_settings(settings: SettingsModel) -> None:
    """Apply settings to the actual system configuration."""
    require_privileged_json(
        "apply-system-settings",
        {
            "hostname": settings.hostname.strip(),
            "timezone": settings.timezone,
            "ssh_port": settings.ssh_port,
            "deny_root_login": settings.deny_root_login,
        },
    )

def _resolve_log_path(name: str) -> str:
    """Resolve a log path inside LOG_DIR and block traversal outside of it."""
    if not name:
        raise Exception("log not found")

    candidate = name if os.path.isabs(name) else os.path.join(LOG_DIR, name)
    root = os.path.realpath(LOG_DIR)
    resolved = os.path.realpath(candidate)

    try:
        if os.path.commonpath([root, resolved]) != root:
            raise Exception("log not found")
    except ValueError:
        raise Exception("log not found")

    if not os.path.isfile(resolved):
        raise Exception("log not found")

    return resolved

def _iter_log_paths():
    """Yield log files under LOG_DIR, including one nested directory level."""
    root = os.path.realpath(LOG_DIR)

    try:
        for current_root, dirs, files in os.walk(root):
            rel_root = os.path.relpath(current_root, root)
            depth = 0 if rel_root == "." else rel_root.count(os.sep) + 1
            if depth >= MAX_LOG_SCAN_DEPTH:
                dirs[:] = []

            for name in files:
                yield os.path.join(current_root, name)
    except Exception:
        return

def _relative_log_name(path: str) -> str:
    """Return the path relative to LOG_DIR for stable API names."""
    return os.path.relpath(os.path.realpath(path), os.path.realpath(LOG_DIR))

def get_log_files() -> list:
    """Get a list of available log files."""
    logs = []

    try:
        for path in _iter_log_paths():
            try:
                stat = os.stat(path)
                logs.append({
                    "name": _relative_log_name(path),
                    "size": stat.st_size,
                    "path": path,
                })
            except Exception:
                pass
    except Exception:
        pass

    logs.sort(key=lambda item: item["name"])
    return logs

def read_log_file(name: str, lines: int = 100) -> str:
    """Read content from a log file."""
    path = _resolve_log_path(name)

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
    _ensure_vpn_dir()
    name = filename or VPN_OVPN_NAME
    safe_name = os.path.basename(name)
    path = os.path.join(VPN_DIR, safe_name)

    secure_write_bytes(path, content)

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
    _ensure_vpn_dir()
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
    _ensure_vpn_dir()
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
    cmd = [
        "openvpn", "--config", ovpn, "--writepid", VPN_PIDFILE,
        "--daemon", "upservx-openvpn",
    ]
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

    require_privileged("stop-openvpn")

    return get_vpn_status()
