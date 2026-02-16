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


def _get_device_uuid(device: str) -> str | None:
    """Get the UUID of a device."""
    try:
        result = subprocess.run(
            ["blkid", "-s", "UUID", "-o", "value", device],
            capture_output=True,
            text=True,
            check=True
        )
        uuid = result.stdout.strip()
        return uuid if uuid else None
    except Exception:
        return None


def _get_filesystem_type(device: str) -> str:
    """Get the filesystem type of a device."""
    try:
        result = subprocess.run(
            ["blkid", "-s", "TYPE", "-o", "value", device],
            capture_output=True,
            text=True,
            check=True
        )
        fstype = result.stdout.strip()
        return fstype if fstype else "auto"
    except Exception:
        return "auto"


def _add_to_fstab(device: str, mountpoint: str, uuid: str | None = None, fstype: str = "auto") -> None:
    """Add an entry to /etc/fstab for persistent mounting."""
    fstab_path = "/etc/fstab"
    
    # Create backup of fstab
    try:
        if os.path.exists(fstab_path):
            backup_path = f"{fstab_path}.backup"
            subprocess.run(["cp", fstab_path, backup_path], check=True)
    except Exception:
        pass  # Continue even if backup fails
    
    # Read current fstab
    existing_entries = []
    if os.path.exists(fstab_path):
        with open(fstab_path, 'r') as f:
            existing_entries = f.readlines()
    
    # Check if entry already exists
    for line in existing_entries:
        if line.strip() and not line.strip().startswith('#'):
            parts = line.split()
            if len(parts) >= 2:
                # Check if mountpoint already has an entry
                if parts[1] == mountpoint:
                    # Entry already exists, don't add duplicate
                    return
                # Check if device already has an entry
                if uuid and parts[0] == f"UUID={uuid}":
                    return
                if parts[0] == device:
                    return
    
    # Determine mount options based on filesystem type
    if fstype in {"ext4", "ext3", "ext2"}:
        options = "defaults,noatime"
    elif fstype in {"ntfs", "ntfs-3g"}:
        options = "defaults,nofail,x-systemd.device-timeout=10"
    elif fstype in {"vfat", "exfat"}:
        options = "defaults,nofail,x-systemd.device-timeout=10,umask=000"
    elif fstype == "xfs":
        options = "defaults,noatime"
    else:
        options = "defaults,nofail"
    
    # Use UUID if available, otherwise use device path
    device_identifier = f"UUID={uuid}" if uuid else device
    
    # Create fstab entry
    fstab_entry = f"{device_identifier}\t{mountpoint}\t{fstype}\t{options}\t0\t2\n"
    
    # Append to fstab
    with open(fstab_path, 'a') as f:
        # Add newline if file doesn't end with one
        if existing_entries and not existing_entries[-1].endswith('\n'):
            f.write('\n')
        f.write(f"# Added by UpservX on {subprocess.check_output(['date'], text=True).strip()}\n")
        f.write(fstab_entry)


def mount_drive(device: str, mountpoint: str) -> None:
    """Mount a drive to the specified mountpoint and add to /etc/fstab for persistence."""
    if not os.path.exists(mountpoint):
        os.makedirs(mountpoint, exist_ok=True)
    
    # Get device UUID and filesystem type
    uuid = _get_device_uuid(device)
    fstype = _get_filesystem_type(device)
    
    # Mount the device
    result = subprocess.run(["mount", device, mountpoint], capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(result.stderr.strip() or "failed to mount")
    
    # Add to fstab for persistent mounting
    try:
        _add_to_fstab(device, mountpoint, uuid, fstype)
    except Exception as e:
        # If fstab update fails, log but don't fail the mount
        print(f"Warning: Failed to update /etc/fstab: {e}")


def _remove_from_fstab(device: str, mountpoint: str | None = None) -> None:
    """Remove an entry from /etc/fstab."""
    fstab_path = "/etc/fstab"
    
    if not os.path.exists(fstab_path):
        return
    
    # Create backup of fstab
    try:
        backup_path = f"{fstab_path}.backup"
        subprocess.run(["cp", fstab_path, backup_path], check=True)
    except Exception:
        pass
    
    # Get UUID of device
    uuid = _get_device_uuid(device)
    
    # Read current fstab
    with open(fstab_path, 'r') as f:
        lines = f.readlines()
    
    # Filter out matching entries
    new_lines = []
    skip_next_comment = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Check if this is a data line (not comment or empty)
        if stripped and not stripped.startswith('#'):
            parts = stripped.split()
            if len(parts) >= 2:
                entry_device = parts[0]
                entry_mount = parts[1]
                
                # Check if this entry matches our device
                should_remove = False
                if entry_device == device:
                    should_remove = True
                elif uuid and entry_device == f"UUID={uuid}":
                    should_remove = True
                elif mountpoint and entry_mount == mountpoint:
                    should_remove = True
                
                if should_remove:
                    # Also skip the "Added by UpservX" comment before this line
                    if new_lines and new_lines[-1].strip().startswith("# Added by UpservX"):
                        new_lines.pop()
                    continue
        
        new_lines.append(line)
    
    # Write back to fstab
    with open(fstab_path, 'w') as f:
        f.writelines(new_lines)


def unmount_drive(device: str | None = None, mountpoint: str | None = None) -> None:
    """Unmount a drive and remove from /etc/fstab.
    
    Args:
        device: Device path (e.g., /dev/sdb1)
        mountpoint: Mount point path (e.g., /mnt/data)
    
    Either device or mountpoint must be provided.
    """
    if not device and not mountpoint:
        raise Exception("Either device or mountpoint must be provided")
    
    # Unmount using mountpoint if provided, otherwise use device
    target = mountpoint if mountpoint else device
    result = subprocess.run(["umount", target], capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(result.stderr.strip() or "failed to unmount")
    
    # Remove from fstab
    try:
        if device:
            _remove_from_fstab(device, mountpoint)
        elif mountpoint:
            # Try to find device from mountpoint
            # This is a fallback, might not always work
            _remove_from_fstab("", mountpoint)
    except Exception as e:
        print(f"Warning: Failed to update /etc/fstab: {e}")


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