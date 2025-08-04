import json
import os
import platform
from typing import Any

from pydantic import BaseModel


class NetworkSettingsModel(BaseModel):
    dns_primary: str = "8.8.8.8"
    dns_secondary: str = "8.8.4.4"


class SettingsModel(BaseModel):
    hostname: str
    timezone: str
    auto_updates: bool
    monitoring: bool
    ssh_port: int = 22
    api_key: str | None = None


SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")
NETWORK_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "network_settings.json")
ISO_DIR = os.path.join(os.path.dirname(__file__), "isos")
os.makedirs(ISO_DIR, exist_ok=True)


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
        api_key=data.get("api_key"),
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

