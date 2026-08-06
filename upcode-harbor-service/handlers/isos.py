"""
ISO file management utilities.
"""

import os
import shutil
import urllib.request
import urllib.parse
from datetime import datetime
from typing import List
from lib.models import ISOInfo
from lib.logger import log_iso


ISO_DIR = os.getenv("UPCODE_HARBOR_ISO_DIR", "/var/lib/libvirt/isos")


def _safe_iso_path(name: str, iso_dir: str) -> str:
    """Return a validated path that is guaranteed to be inside iso_dir."""
    # Strip path separators so names like '../../etc/passwd' are rejected
    safe_name = os.path.basename(name)
    resolved = os.path.realpath(os.path.join(iso_dir, safe_name))
    if not resolved.startswith(os.path.realpath(iso_dir)):
        raise Exception("Invalid ISO name")
    return resolved


def get_iso_dir() -> str:
    """Return the installer-managed ISO directory without mutating the host."""

    return ISO_DIR


def _get_writable_iso_dir() -> str:
    iso_dir = get_iso_dir()
    if not os.path.isdir(iso_dir) or not os.access(iso_dir, os.W_OK):
        raise RuntimeError(
            "ISO storage is unavailable; install the virtualization profile"
        )
    return iso_dir


def guess_iso_info(filename: str) -> tuple[str, str, str]:
    """Guess ISO information from filename."""
    lower = filename.lower()
    typ = "Windows" if "win" in lower or "windows" in lower else "Linux"
    arch = "arm64" if "arm64" in lower or "aarch64" in lower else "x86_64"
    version = filename.rsplit(".", 1)[0]
    return typ, version, arch


def get_iso_files() -> List[ISOInfo]:
    """Get list of available ISO files."""
    files: List[ISOInfo] = []
    iso_dir = get_iso_dir()
    
    if not os.path.isdir(iso_dir):
        return files
    
    for idx, name in enumerate(sorted(os.listdir(iso_dir)), start=1):
        if not name.lower().endswith(".iso"):
            continue
        
        path = os.path.join(iso_dir, name)
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


def download_iso(url: str, name: str = None) -> ISOInfo:
    """Download an ISO file from a URL."""
    if not url:
        raise Exception("url required")
    
    # Block SSRF: only allow http/https with public destinations
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise Exception("Only http/https URLs are allowed")
    hostname = parsed.hostname or ""
    if hostname in ("localhost", "127.0.0.1", "::1") or hostname.startswith("192.168.") or hostname.startswith("10.") or hostname.startswith("172."):
        raise Exception("Downloads from private/local addresses are not allowed")
    
    filename = name or os.path.basename(parsed.path) or "download.iso"
    if not filename.lower().endswith(".iso"):
        filename += ".iso"
    
    iso_dir = _get_writable_iso_dir()
    dest = _safe_iso_path(filename, iso_dir)
    
    try:
        with urllib.request.urlopen(url) as resp, open(dest, "wb") as out:
            shutil.copyfileobj(resp, out)
    except Exception as e:
        if os.path.exists(dest):
            os.remove(dest)
        log_iso(f"Failed to download ISO [{filename}] from [{url}]: {e}", error=True)
        raise Exception(str(e))
    
    stat = os.stat(dest)
    os.chmod(dest, 0o640)
    typ, version, arch = guess_iso_info(filename)
    log_iso(f"Downloaded ISO [{filename}] from [{url}] ({round(stat.st_size / (1024**3), 1)} GB)")
    
    return ISOInfo(
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


def save_uploaded_iso(file_content: bytes, filename: str) -> ISOInfo:
    """Save uploaded ISO file content."""
    if not filename.lower().endswith(".iso"):
        raise Exception("invalid iso file")
    
    iso_dir = _get_writable_iso_dir()
    dest = _safe_iso_path(filename, iso_dir)
    
    with open(dest, "wb") as f:
        f.write(file_content)
    os.chmod(dest, 0o640)
    
    stat = os.stat(dest)
    typ, version, arch = guess_iso_info(filename)
    log_iso(f"Uploaded ISO [{filename}] ({round(stat.st_size / (1024**3), 1)} GB)")
    
    return ISOInfo(
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


def delete_iso(name: str) -> None:
    """Delete an ISO file."""
    iso_dir = _get_writable_iso_dir()
    path = _safe_iso_path(name, iso_dir)
    
    if not os.path.isfile(path):
        raise Exception("iso not found")
    
    os.remove(path)
    log_iso(f"Deleted ISO [{name}]")


def get_iso_path(name: str) -> str:
    """Get the full path to an ISO file."""
    iso_dir = get_iso_dir()
    path = _safe_iso_path(name, iso_dir)
    
    if not os.path.isfile(path):
        raise Exception("iso not found")
    
    return path
