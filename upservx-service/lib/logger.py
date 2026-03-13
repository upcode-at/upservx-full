"""
UpservX Structured Activity Logger

Writes human-readable activity entries to /var/log/upservx/activity.log
in the format:

  YYYY-MM-DD HH:MM:SS [TAG] Message

Usage:
    from lib.logger import log_backup, log_container, log_auth, ...

    log_backup("Successfully connected to Backup Server [my-nas]")
    log_container("Started container [nginx]")
    log_auth("Login successful for user [admin]")
"""

import os
import logging
from datetime import datetime

ACTIVITY_LOG_FILE = "/var/log/upservx/activity.log"

try:
    os.makedirs(os.path.dirname(ACTIVITY_LOG_FILE), exist_ok=True)
except OSError:
    pass

_logger = logging.getLogger("upservx.activity")

def _ensure_file_handler() -> None:
    for h in _logger.handlers:
        if isinstance(h, logging.FileHandler) and h.baseFilename == os.path.abspath(ACTIVITY_LOG_FILE):
            return
    try:
        fh = logging.FileHandler(ACTIVITY_LOG_FILE, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(message)s"))
        _logger.addHandler(fh)
        _logger.propagate = True
        _logger.setLevel(logging.INFO)
    except OSError:
        _logger.propagate = True

_ensure_file_handler()


def _write(tag: str, message: str, level: str = "INFO") -> None:
    """Format and write a structured log entry."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp} [{tag}] {message}"
    if level == "ERROR":
        _logger.error(line)
    elif level == "WARNING":
        _logger.warning(line)
    else:
        _logger.info(line)


def log_auth(message: str, error: bool = False) -> None:
    """Authentication events (login, logout, failed attempts)."""
    _write("AUTH", message, "ERROR" if error else "INFO")


def log_container(message: str, error: bool = False) -> None:
    """Container lifecycle events (create, start, stop, delete)."""
    _write("CONTAINER", message, "ERROR" if error else "INFO")


def log_vm(message: str, error: bool = False) -> None:
    """Virtual Machine events (create, start, stop, snapshot, delete)."""
    _write("VM", message, "ERROR" if error else "INFO")


def log_backup(message: str, error: bool = False) -> None:
    """Backup events (connect, execute, complete, fail)."""
    _write("BACKUP", message, "ERROR" if error else "INFO")


def log_storage(message: str, error: bool = False) -> None:
    """Storage events (mount, unmount, format, ZFS pool)."""
    _write("STORAGE", message, "ERROR" if error else "INFO")


def log_network(message: str, error: bool = False) -> None:
    """Network events (interface config, settings save)."""
    _write("NETWORK", message, "ERROR" if error else "INFO")


def log_user(message: str, error: bool = False) -> None:
    """User & group management events."""
    _write("USER", message, "ERROR" if error else "INFO")


def log_service(message: str, error: bool = False) -> None:
    """SystemD service events (start, stop, enable, disable)."""
    _write("SERVICE", message, "ERROR" if error else "INFO")


def log_firewall(message: str, error: bool = False) -> None:
    """Firewall rule events."""
    _write("FIREWALL", message, "ERROR" if error else "INFO")


def log_proxy(message: str, error: bool = False) -> None:
    """Reverse proxy / Nginx / SSL certificate events."""
    _write("PROXY", message, "ERROR" if error else "INFO")


def log_appstore(message: str, error: bool = False) -> None:
    """App Store deployment events."""
    _write("APPSTORE", message, "ERROR" if error else "INFO")


def log_iso(message: str, error: bool = False) -> None:
    """ISO image events (download, upload, delete)."""
    _write("ISO", message, "ERROR" if error else "INFO")


def log_system(message: str, error: bool = False) -> None:
    """General system / API lifecycle events."""
    _write("SYSTEM", message, "ERROR" if error else "INFO")


def log_ssh(message: str, error: bool = False) -> None:
    """SSH key management events."""
    _write("SSH", message, "ERROR" if error else "INFO")


def log_vpn(message: str, error: bool = False) -> None:
    """VPN events (start, stop, upload)."""
    _write("VPN", message, "ERROR" if error else "INFO")
