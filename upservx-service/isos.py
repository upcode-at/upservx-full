"""
ISO file management utilities.
"""

import os
import shutil
import urllib.request
import urllib.parse
from datetime import datetime
from typing import List
from models import ISOInfo


def get_iso_dir() -> str:
    """Get the ISO directory path."""
    iso_dir = os.path.join(os.path.dirname(__file__), "isos")
    os.makedirs(iso_dir, exist_ok=True)
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
    
    filename = name or os.path.basename(urllib.parse.urlparse(url).path) or "download.iso"
    if not filename.lower().endswith(".iso"):
        filename += ".iso"
    
    iso_dir = get_iso_dir()
    dest = os.path.join(iso_dir, filename)
    
    try:
        with urllib.request.urlopen(url) as resp, open(dest, "wb") as out:
            shutil.copyfileobj(resp, out)
    except Exception as e:
        if os.path.exists(dest):
            os.remove(dest)
        raise Exception(str(e))
    
    stat = os.stat(dest)
    typ, version, arch = guess_iso_info(filename)
    
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
    
    iso_dir = get_iso_dir()
    dest = os.path.join(iso_dir, filename)
    
    with open(dest, "wb") as f:
        f.write(file_content)
    
    stat = os.stat(dest)
    typ, version, arch = guess_iso_info(filename)
    
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
    iso_dir = get_iso_dir()
    path = os.path.join(iso_dir, name)
    
    if not os.path.isfile(path):
        raise Exception("iso not found")
    
    os.remove(path)


def get_iso_path(name: str) -> str:
    """Get the full path to an ISO file."""
    iso_dir = get_iso_dir()
    path = os.path.join(iso_dir, name)
    
    if not os.path.isfile(path):
        raise Exception("iso not found")
    
    return path