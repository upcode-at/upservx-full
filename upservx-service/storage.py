"""
Storage and filesystem management utilities including drives and ZFS.
"""

import os
import json
import subprocess
import shutil
import psutil
from typing import List
from models import DriveInfo, ZFSPoolInfo, ZFSDeviceInfo


def _drive_type(dev: str) -> str:
    """Return the type for a device or partition."""
    name = os.path.basename(dev)
    # Resolve base device if this is a partition
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


def get_zfs_pools() -> List[ZFSPoolInfo]:
    """Return a list of ZFS pools with their member devices and usage."""
    if shutil.which("zpool") is None:
        return []

    size_info: dict[str, dict[str, int]] = {}
    result = subprocess.run(
        ["zpool", "list", "-H", "-p", "-o", "name,size,alloc,free"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4:
                name, size, alloc, free = parts[:4]
                size_info[name] = {
                    "size": int(size),
                    "used": int(alloc),
                    "available": int(free),
                }

    mountpoints: dict[str, str] = {}
    zfs_res = subprocess.run(
        ["zfs", "list", "-H", "-o", "name,mountpoint"],
        capture_output=True,
        text=True,
    )
    if zfs_res.returncode == 0:
        for line in zfs_res.stdout.splitlines():
            try:
                name, mnt = line.split("\t")
            except ValueError:
                continue
            if "/" not in name:
                mountpoints[name] = mnt

    status = subprocess.run(["zpool", "status"], capture_output=True, text=True)
    if status.returncode != 0:
        return []

    pools: List[ZFSPoolInfo] = []
    lines = status.stdout.splitlines()
    pool: dict | None = None
    in_config = False
    for line in lines:
        if line.startswith("  pool:"):
            if pool:
                pools.append(ZFSPoolInfo(**pool))
            name = line.split()[1]
            info = size_info.get(name, {"size": 0, "used": 0, "available": 0})
            pool = {
                "name": name,
                "devices": [],
                "type": "stripe",
                "size": round(info["size"] / (1024 ** 3)),
                "used": round(info["used"] / (1024 ** 3)),
                "available": round(info["available"] / (1024 ** 3)),
                "mountpoint": mountpoints.get(name, ""),
            }
            in_config = False
        elif pool and line.startswith(" state:"):
            pass
        elif pool and line.startswith("config:"):
            in_config = True
        elif pool and in_config:
            stripped = line.strip()
            if not stripped or stripped.startswith("NAME"):
                continue
            parts = stripped.split()
            token = parts[0]
            state = parts[1] if len(parts) > 1 else ""
            if token == pool["name"]:
                continue
            if token.startswith("mirror") or token.startswith("raidz"):
                pool["type"] = token.split("-")[0]
                continue
            device = token
            if not token.startswith("/"):
                device = f"/dev/{token}"
            pool["devices"].append({"path": device, "status": state})
        if pool and line.startswith("errors:"):
            pass
    if pool:
        pools.append(ZFSPoolInfo(**pool))
    return pools


def get_drives() -> List[DriveInfo]:
    """Return information for all physical drives including unmounted ones."""
    drives: List[DriveInfo] = []
    try:
        output = subprocess.check_output(
            ["lsblk", "-b", "-J", "-o", "NAME,TYPE,SIZE,FSTYPE,MOUNTPOINT"],
            text=True,
        )
        data = json.loads(output)
    except Exception:
        data = {"blockdevices": []}

    def add_device(node: dict) -> None:
        if node.get("type") not in {"disk", "part"}:
            for child in node.get("children", []):
                add_device(child)
            return
        if node.get("type") == "disk" and node.get("children"):
            for child in node.get("children", []):
                add_device(child)
            return
        name = node.get("name")
        if not name:
            return
        dev = f"/dev/{name}"
        if dev.startswith("/dev/loop"):
            return
        mountpoint = node.get("mountpoint") or ""
        try:
            size = int(node.get("size", 0))
        except Exception:
            size = 0
        if size <= 0:
            return
        usage = None
        if mountpoint:
            try:
                usage = psutil.disk_usage(mountpoint)
            except Exception:
                pass
        drives.append(
            DriveInfo(
                device=dev,
                name=name,
                type=_drive_type(dev),
                size=round(size / (1024 ** 3)),
                used=round((usage.used if usage else 0) / (1024 ** 3)),
                available=round((usage.free if usage else 0) / (1024 ** 3)),
                filesystem=node.get("fstype") or "",
                mountpoint=mountpoint,
                mounted=bool(mountpoint),
            )
        )
        for child in node.get("children", []):
            add_device(child)

    for dev in data.get("blockdevices", []):
        add_device(dev)

    # Remove devices that are part of ZFS pools
    for pool in get_zfs_pools():
        for dev in pool.devices:
            drives = [d for d in drives if d.device != dev.path]

    unique = {}
    for d in drives:
        if d.device not in unique:
            unique[d.device] = d
    return list(unique.values())


def mount_drive(device: str, mountpoint: str) -> None:
    """Mount a drive to the specified mountpoint."""
    if not os.path.exists(mountpoint):
        os.makedirs(mountpoint, exist_ok=True)
    result = subprocess.run(["mount", device, mountpoint], capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(result.stderr.strip() or "failed to mount")


def format_drive(device: str, filesystem: str, label: str | None = None) -> None:
    """Format a drive with the specified filesystem."""
    fs = filesystem.lower()
    if fs == "ext4":
        cmd = ["mkfs.ext4", "-F"]
    elif fs == "ntfs":
        cmd = ["mkfs.ntfs", "-F"]
    elif fs == "fat32":
        cmd = ["mkfs.vfat", "-F", "32"]
    elif fs == "exfat":
        cmd = ["mkfs.exfat"]
    elif fs == "zfs":
        if shutil.which("zpool") is None:
            raise Exception("zfs not installed")
        pool = label or os.path.basename(device)
        cmd = ["zpool", "create", "-f", pool, device]
    else:
        raise Exception("unsupported filesystem")
    
    if label and fs != "zfs":
        if fs in {"ext4", "ntfs"}:
            cmd.extend(["-L", label])
        else:
            cmd.extend(["-n", label])
    
    if fs != "zfs":
        cmd.append(device)
    
    # Unmount the device first in case it is currently mounted
    subprocess.run(["umount", device], capture_output=True)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(result.stderr.strip() or "failed to format")


def create_zfs_pool(name: str, devices: List[str], raid: str = "stripe") -> None:
    """Create a new ZFS pool."""
    if shutil.which("zpool") is None:
        raise Exception("zfs not installed")
    if not devices:
        raise Exception("no devices specified")
    
    cmd = ["zpool", "create", "-f", name]
    raid_lower = raid.lower()
    if raid_lower == "mirror":
        cmd.append("mirror")
    elif raid_lower in {"raidz", "raidz2", "raidz3"}:
        cmd.append(raid_lower)
    elif raid_lower != "stripe":
        raise Exception("invalid raid level")
    
    cmd.extend(devices)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(result.stderr.strip() or "failed to create pool")