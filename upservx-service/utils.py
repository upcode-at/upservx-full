import os
import subprocess
from datetime import datetime
from typing import List

from fastapi import HTTPException

from models import ISOInfo
from settings import ISO_DIR


def run_subprocess(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run a subprocess, logging the command and raising HTTPException on failure."""
    cmd_str = " ".join(cmd)
    print("Running command:", cmd_str)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip() or "failed"
        raise HTTPException(status_code=400, detail=f"{cmd_str}\n{msg}")
    return result


def parse_ports(port_str: str) -> List[str]:
    """Split Docker style port mappings into a list."""
    if not port_str:
        return []
    return [p.strip() for p in port_str.split(',') if p.strip()]


def parse_docker_size(size: str) -> float:
    size = size.lower().strip()
    if size.endswith("gb"):
        try:
            return float(size[:-2].strip()) * 1000
        except ValueError:
            return 0.0
    if size.endswith("mb"):
        try:
            return float(size[:-2].strip())
        except ValueError:
            return 0.0
    return 0.0


def guess_iso_info(filename: str) -> tuple[str, str, str]:
    lower = filename.lower()
    typ = "Windows" if "win" in lower or "windows" in lower else "Linux"
    arch = "arm64" if "arm64" in lower or "aarch64" in lower else "x86_64"
    version = filename.rsplit(".", 1)[0]
    return typ, version, arch


def get_iso_files() -> List[ISOInfo]:
    files: List[ISOInfo] = []
    if not os.path.isdir(ISO_DIR):
        return files
    for idx, name in enumerate(sorted(os.listdir(ISO_DIR)), start=1):
        if not name.lower().endswith(".iso"):
            continue
        path = os.path.join(ISO_DIR, name)
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


def drive_type(dev: str) -> str:
    """Return the type for a device or partition."""
    name = os.path.basename(dev)
    try:
        base = os.path.basename(os.path.realpath(os.path.join("/sys/class/block", name, "..")))
    except Exception:
        base = name
    rotational = f"/sys/block/{base}/queue/rotational"
    removable = f"/sys/block/{base}/removable"
    try:
        with open(removable) as f:
            if f.read().strip() == "1":
                return "USB"
    except Exception:
        pass
    try:
        with open(rotational) as f:
            if f.read().strip() == "0":
                return "SSD"
    except Exception:
        pass
    if name.startswith("mmc"):
        return "SD"
    return "HDD"
