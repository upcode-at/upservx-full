"""
Virtual machine management utilities using libvirt/KVM.
"""

import os
import json
import subprocess
import shutil
import tempfile
import pwd
import grp
from typing import List
from datetime import datetime
from lib.models import VirtualMachine
from lib.logger import log_vm
from lib.secure_store import ensure_config_directory, secure_write_json
from handlers.notifications import notify

import time

VM_FILE = "/etc/upcode-harbor/vms.json"

def set_libvirt_permissions(path: str) -> None:
    """Set ownership and permissions for libvirt-qemu user."""
    try:
        uid = pwd.getpwnam("libvirt-qemu").pw_uid
        gid = grp.getgrnam("libvirt-qemu").gr_gid
        
        os.chown(path, uid, gid)
        
        if os.path.isdir(path):
            os.chmod(path, 0o755)
        else:
            os.chmod(path, 0o644)
    except (KeyError, PermissionError) as e:
        log_vm(f"Warning: could not set libvirt permissions on [{path}]: {e}", error=True)

def ensure_parent_permissions(path: str) -> None:
    """Ensure all parent directories are accessible (executable) for libvirt-qemu."""
    try:
        gid = grp.getgrnam("libvirt-qemu").gr_gid
        
        # Walk up the directory tree and ensure execute permission for group
        current = os.path.dirname(path)
        while current and current != "/":
            try:
                stat_info = os.stat(current)
                # Add execute permission for group if not already set (o+rx for group access)
                current_mode = stat_info.st_mode
                # Ensure at least o+rx (others can read and execute) so libvirt-qemu can traverse
                new_mode = current_mode | 0o755
                if current_mode != new_mode:
                    os.chmod(current, new_mode)
            except (PermissionError, OSError) as e:
                log_vm(f"Warning: could not set permissions on parent directory [{current}]: {e}", error=True)
                break
            
            parent = os.path.dirname(current)
            if parent == current:  # Reached root
                break
            current = parent
    except (KeyError, PermissionError) as e:
        log_vm(f"Warning: could not ensure parent permissions for [{path}]: {e}", error=True)

def ensure_vlan_interface(parent: str, vlan_id: int) -> str:
    """Ensure a VLAN sub-interface exists for the given parent interface and VLAN ID.
    Returns the VLAN interface name (e.g., eth0.100).
    """
    if vlan_id < 1 or vlan_id > 4094:
        raise Exception(f"Invalid VLAN ID {vlan_id}: must be between 1 and 4094")
    vlan_iface = f"{parent}.{vlan_id}"
    result = subprocess.run(["ip", "link", "show", vlan_iface], capture_output=True, text=True)
    if result.returncode == 0:
        # Interface already exists, make sure it is up
        subprocess.run(["ip", "link", "set", vlan_iface, "up"], capture_output=True)
        return vlan_iface
    try:
        subprocess.run(
            ["ip", "link", "add", "link", parent, "name", vlan_iface, "type", "vlan", "id", str(vlan_id)],
            check=True, capture_output=True,
        )
        subprocess.run(["ip", "link", "set", vlan_iface, "up"], check=True, capture_output=True)
        log_vm(f"Created VLAN sub-interface [{vlan_iface}] on [{parent}] (VLAN ID {vlan_id})")
        return vlan_iface
    except subprocess.CalledProcessError as e:
        log_vm(f"Warning: could not create VLAN interface [{vlan_iface}]: {e}", error=True)
        return parent


def ensure_bridge_for_interface(interface: str) -> str:
    """Ensure a Linux bridge exists for the given physical interface.
    Returns the bridge name (e.g., br0).
    Transfers IP configuration from interface to bridge.
    """
    bridge_name = f"br-{interface}"
    
    result = subprocess.run(["ip", "link", "show", bridge_name], capture_output=True, text=True)
    if result.returncode == 0:
        return bridge_name
    
    try:
        ip_info = subprocess.run(["ip", "addr", "show", interface], capture_output=True, text=True, check=True)
        
        import re
        ip_addresses = []
        for line in ip_info.stdout.splitlines():
            match = re.search(r'inet6?\s+([^\s]+)', line)
            if match:
                ip_addresses.append(match.group(1))
        
        route_info = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True)
        gateway = None
        for line in route_info.stdout.splitlines():
            if f"dev {interface}" in line:
                match = re.search(r'via\s+([^\s]+)', line)
                if match:
                    gateway = match.group(1)
        
        subprocess.run(["ip", "link", "add", "name", bridge_name, "type", "bridge"], check=True, capture_output=True)
        
        for ip_addr in ip_addresses:
            subprocess.run(["ip", "addr", "del", ip_addr, "dev", interface], capture_output=True)
        
        # Add physical interface to bridge (must be done before bringing bridge up)
        subprocess.run(["ip", "link", "set", interface, "master", bridge_name], check=True, capture_output=True)
        
        subprocess.run(["ip", "link", "set", bridge_name, "up"], check=True, capture_output=True)
        
        subprocess.run(["ip", "link", "set", interface, "up"], check=True, capture_output=True)
        
        for ip_addr in ip_addresses:
            subprocess.run(["ip", "addr", "add", ip_addr, "dev", bridge_name], capture_output=True)
        
        if gateway:
            subprocess.run(["ip", "route", "add", "default", "via", gateway, "dev", bridge_name], capture_output=True)
        
        log_vm(f"Created bridge [{bridge_name}] for interface [{interface}] with IP configuration transferred")
        return bridge_name
    except subprocess.CalledProcessError as e:
        log_vm(f"Warning: could not create bridge for [{interface}]: {e}", error=True)
        return interface

def load_vms() -> List[VirtualMachine]:
    """Load virtual machines from the JSON file."""
    if os.path.exists(VM_FILE):
        try:
            with open(VM_FILE) as f:
                data = json.load(f)
            return [VirtualMachine(**vm) for vm in data]
        except Exception:
            return []
    return []

def save_vms(vms: List[VirtualMachine]) -> None:
    """Save virtual machines to the JSON file."""
    secure_write_json(VM_FILE, [vm.model_dump() for vm in vms])

def parse_virsh_list() -> dict[str, str]:
    """Parse virsh list output to get VM statuses."""
    statuses: dict[str, str] = {}
    if shutil.which("virsh") is None:
        return statuses
    result = subprocess.run(["virsh", "list", "--all"], capture_output=True, text=True)
    if result.returncode != 0:
        return statuses
    for line in result.stdout.splitlines()[2:]:
        parts = line.split()
        if len(parts) >= 3:
            status = " ".join(parts[2:])
            if status in ["laufend", "läuft", "running"]:
                status = "running"
            elif status in ["ausgeschaltet", "shut off", "shut", "off"]:
                status = "stopped"
            elif status == "pausiert":
                status = "paused"
            statuses[parts[1]] = status
    return statuses

def get_vm_stats(name: str) -> dict[str, float]:
    """Get VM resource usage statistics using virsh commands."""
    stats = {"cpu_usage": 0.0, "memory_usage": 0.0}
    
    if shutil.which("virsh") is None:
        return stats
    
    try:
        mem_result = subprocess.run(
            ["virsh", "dommemstat", name],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if mem_result.returncode == 0:
            available_mem = None
            usable_mem = None
            actual_mem = None
            rss_mem = None
            
            for line in mem_result.stdout.splitlines():
                line = line.strip()
                if line.startswith("available "):
                    # Total memory as seen by the guest OS in KB
                    available_mem = int(line.split()[1])
                elif line.startswith("usable "):
                    # Memory available for applications (free + reclaimable)
                    usable_mem = int(line.split()[1])
                elif line.startswith("actual "):
                    # Total memory allocated to VM in KB
                    actual_mem = int(line.split()[1])
                elif line.startswith("rss "):
                    # Resident set size - physical memory used on host
                    rss_mem = int(line.split()[1])
            
            # Prefer guest-reported values (available/usable) over host values (rss/actual)
            if available_mem and usable_mem and available_mem > 0:
                # Best case: guest agent is running
                # usable = free + reclaimable, so used = available - usable
                memory_used = available_mem - usable_mem
                stats["memory_usage"] = round((memory_used / available_mem) * 100, 1)
            elif actual_mem and rss_mem and actual_mem > 0:
                # Fallback: use host-side RSS (less accurate but better than nothing)
                # This shows how much physical RAM the QEMU process uses
                stats["memory_usage"] = round((rss_mem / actual_mem) * 100, 1)
            elif actual_mem:
                # No data available, return 0
                stats["memory_usage"] = 0.0
        
        pidof_result = subprocess.run(
            ["pgrep", "-f", f"guest={name},"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if pidof_result.returncode != 0 or not pidof_result.stdout.strip():
            pidof_result = subprocess.run(
                ["pgrep", "-f", f"name={name}"],
                capture_output=True,
                text=True,
                timeout=5
            )
        
        if pidof_result.returncode == 0 and pidof_result.stdout.strip():
            pid = pidof_result.stdout.strip().split()[0]
            
            # Get CPU stats twice with a small delay to calculate current usage
            try:
                with open(f"/proc/{pid}/stat", "r") as f:
                    stat1 = f.read().split()
                    utime1 = int(stat1[13])
                    stime1 = int(stat1[14])
                
                with open("/proc/stat", "r") as f:
                    cpu_line1 = f.readline().split()
                    cpu_total1 = sum(int(x) for x in cpu_line1[1:])
                
                time.sleep(0.1)
                
                with open(f"/proc/{pid}/stat", "r") as f:
                    stat2 = f.read().split()
                    utime2 = int(stat2[13])
                    stime2 = int(stat2[14])
                
                with open("/proc/stat", "r") as f:
                    cpu_line2 = f.readline().split()
                    cpu_total2 = sum(int(x) for x in cpu_line2[1:])
                
                process_time = (utime2 + stime2) - (utime1 + stime1)
                total_time = cpu_total2 - cpu_total1
                
                if total_time > 0:
                    cpu_usage = (process_time / total_time) * 100
                    stats["cpu_usage"] = round(cpu_usage, 1)
                    
            except (FileNotFoundError, ValueError, IndexError, ZeroDivisionError):
                pass
        
    except (subprocess.TimeoutExpired, Exception) as e:
        log_vm(f"Warning: could not get stats for VM [{name}]: {e}", error=True)
    
    return stats

def get_vnc_info(name: str) -> dict:
    """Get VNC connection info for a VM."""
    if shutil.which("virsh") is None:
        raise Exception("virsh not installed")
    
    result = subprocess.run(["virsh", "domdisplay", name], capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception("VM not running or no display configured")
    
    display = result.stdout.strip()
    if not display.startswith("vnc://"):
        raise Exception("No VNC display configured")
    
    # Parse vnc://127.0.0.1:5900 format
    parts = display.replace("vnc://", "").split(":")
    host = parts[0]
    port = int(parts[1]) if len(parts) > 1 else 5900
    
    return {"host": host, "port": port, "display": display}

def _disk_extension(fmt: str) -> str:
    """Return the file extension for a given qemu-img format."""
    return {"qcow2": ".qcow2", "raw": ".img", "vmdk": ".vmdk"}.get(fmt, f".{fmt}")


def _validate_disk_format(fmt: str) -> str:
    """Validate and normalise disk format. Falls back to qcow2 for unknown formats."""
    allowed = {"qcow2", "raw", "vmdk"}
    fmt = fmt.lower().strip()
    return fmt if fmt in allowed else "qcow2"


def create_vm(name: str, cpu: int, memory: int, iso: str, disks: List, iso_dir: str,
              network_mode: str = "nat", bridge_interface: str | None = None,
              vlan_id: int | None = None, network_name: str | None = None,
              autostart: bool = False,
              cloud_init: str | None = None, storage_path: str | None = None) -> VirtualMachine:
    """Create a new virtual machine using virt-install.

    Supports optional cloud-init user-data (string). If `cloud_init` is provided
    a small seed ISO will be created and attached as a CD-ROM.
    network_mode: "nat" (virbr0), "bridge" (direct to physical), "internal" (libvirt network), or "none" (no network)
    bridge_interface: physical interface name for bridge mode (e.g. "wlp3s0", "enp0s31f6")
    vlan_id: optional VLAN tag (1-4094) for bridge mode; creates a VLAN sub-interface
    network_name: libvirt network name for internal mode (e.g. "mynet")
    storage_path: optional path to mounted drive for VM disks (e.g., /mnt/ssd1)
                  VM disks will be stored in {storage_path}/vms/{vm_name}/
    """
    if shutil.which("virt-install") is None:
        raise Exception("virt-install not installed")

    iso_path = os.path.join(iso_dir, iso) if iso else None
    if iso_path and not os.path.isfile(iso_path):
        raise Exception("iso not found")

    if shutil.which("qemu-img") is None:
        raise Exception("qemu-img not installed")

    if storage_path and os.path.isdir(storage_path):
        vms_root = os.path.join(storage_path, "vms")
        base_dir = os.path.join(vms_root, name)
        
        ensure_parent_permissions(vms_root)
        
        if not os.path.exists(vms_root):
            os.makedirs(vms_root, exist_ok=True)
            set_libvirt_permissions(vms_root)
        
        os.makedirs(base_dir, exist_ok=True)
        set_libvirt_permissions(base_dir)
    else:
        base_dir = "/var/lib/libvirt/images"

    disk_args = []
    disk_paths = []
    _default_disk = {"size": 20, "format": "qcow2"}
    for idx, disk_cfg in enumerate(disks or [_default_disk], start=1):
        size = disk_cfg.get("size", 20) if isinstance(disk_cfg, dict) else getattr(disk_cfg, "size", 20)
        fmt = _validate_disk_format(disk_cfg.get("format", "qcow2") if isinstance(disk_cfg, dict) else getattr(disk_cfg, "format", "qcow2"))
        ext = _disk_extension(fmt)
        disk_path = os.path.join(base_dir, f"{name}_{idx}{ext}")
        disk_paths.append(disk_path)
        r = subprocess.run(["qemu-img", "create", "-f", fmt, disk_path, f"{size}G"], capture_output=True, text=True)
        if r.returncode != 0:
            raise Exception(r.stderr.strip() or "failed to create disk")
        set_libvirt_permissions(disk_path)
        disk_args.extend(["--disk", f"path={disk_path},format={fmt},size={size}"])

    seed_iso_path = None
    tempdir = None
    try:
        if cloud_init:
            tempdir = tempfile.mkdtemp(prefix=f"vm_{name}_")
            user_data_path = os.path.join(tempdir, "user-data")
            meta_data_path = os.path.join(tempdir, "meta-data")
            with open(user_data_path, "w") as f:
                f.write(cloud_init)
            # minimal meta-data
            with open(meta_data_path, "w") as f:
                f.write(f"instance-id: {name}\nlocal-hostname: {name}\n")

            seed_iso_path = os.path.join(base_dir, f"{name}_seed.iso")
            # prefer cloud-localds if available
            if shutil.which("cloud-localds"):
                r = subprocess.run(["cloud-localds", seed_iso_path, user_data_path, meta_data_path], capture_output=True, text=True)
            elif shutil.which("genisoimage") or shutil.which("mkisofs"):
                tool = shutil.which("genisoimage") or shutil.which("mkisofs")
                r = subprocess.run([tool, "-output", seed_iso_path, "-volid", "cidata", "-joliet", "-rock", user_data_path, meta_data_path], capture_output=True, text=True)
            else:
                raise Exception("no tool available to create cloud-init ISO (install cloud-localds or genisoimage)")

            if r.returncode != 0:
                raise Exception(r.stderr.strip() or "failed to create cloud-init iso")

            set_libvirt_permissions(seed_iso_path)

            disk_args.extend(["--disk", f"path={seed_iso_path},device=cdrom"])

        network_args = []
        network_bridge = "virbr0"  # default for storage
        if network_mode == "nat":
            network_args = ["--network", "network=default"]
            network_bridge = "virbr0"
        elif network_mode == "bridge":
            if not bridge_interface:
                raise Exception("bridge_interface required for bridge mode")

            phys_iface = bridge_interface
            if vlan_id:
                phys_iface = ensure_vlan_interface(bridge_interface, vlan_id)
            actual_bridge = ensure_bridge_for_interface(phys_iface)
            network_args = ["--network", f"bridge={actual_bridge}"]
            network_bridge = actual_bridge
        elif network_mode == "internal":
            if not network_name:
                raise Exception("network_name required for internal network mode")
            network_args = ["--network", f"network={network_name}"]
            network_bridge = f"network:{network_name}"
        elif network_mode == "unconfigured":
            # Create unconfigured network interface - requires manual configuration
            # Using type=ethernet creates a network interface without automatic configuration
            network_args = ["--network", "type=ethernet,model=virtio"]
            network_bridge = "unconfigured"
        elif network_mode == "none":
            network_args = ["--network", "none"]
            network_bridge = "none"
        else:
            network_args = ["--network", "network=default"]
            network_bridge = "virbr0"

        cmd = [
            "virt-install",
            "--name", name,
            "--ram", str(memory),
            "--vcpus", str(cpu),
            *disk_args,
            "--os-variant", "generic",
            *network_args,
            "--graphics", "vnc",
            "--hvm",
            "--noautoconsole",
        ]

        if iso_path:
            cmd.extend([
                "--disk", f"path={iso_path},device=cdrom,readonly=on",
                "--boot", "cdrom,hd"
            ])
        else:
            cmd.extend(["--boot", "hd"])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(result.stderr.strip() or "failed to create")

        if autostart:
            r2 = subprocess.run(["virsh", "autostart", name], capture_output=True, text=True)
            if r2.returncode != 0:
                # non-fatal, but report
                raise Exception(r2.stderr.strip() or "failed to set autostart")

        vms = load_vms()
        vm = VirtualMachine(
            id=len(vms) + 1,
            name=name,
            status="running",
            cpu=cpu,
            memory=memory,
            iso=iso or "",
            disks=disk_paths,
            created=datetime.utcnow().date().isoformat(),
            autostart=autostart,
            network_bridge=network_bridge,
            vlan_id=vlan_id if network_mode == "bridge" else None,
            cloud_init_iso=seed_iso_path,
            storage_path=storage_path,
        )
        log_vm(f"Created VM [{name}] (CPU: {cpu}, Memory: {memory} MB, Network: {network_bridge})")
        vms.append(vm)
        save_vms(vms)
        notify("vm_create", f"VM '{name}' created | CPU: {cpu} core(s) | Memory: {memory} MB | Network: {network_bridge} | Disks: {len(disk_paths)}")
        return vm
    finally:
        # tempdir may be kept for debugging, do not delete seed iso in /var/lib/libvirt/images
        if tempdir and os.path.isdir(tempdir):
            try:
                shutil.rmtree(tempdir)
            except Exception:
                pass

def update_vm(name: str, cpu: int | None = None, memory: int | None = None,
             iso: str | None = None, add_disks: List | None = None, iso_dir: str = "",
             autostart: bool | None = None, remove_disks: List[str] | None = None,
             network_mode: str | None = None, bridge_interface: str | None = None,
             vlan_id: int | None = None, network_name: str | None = None,
             storage_path: str | None = None) -> VirtualMachine:
    """Update an existing virtual machine configuration.
    
    storage_path: optional path to mounted drive for new VM disks (e.g., /mnt/ssd1)
                  New disks will be stored in {storage_path}/vms/{vm_name}/
    """
    if shutil.which("virsh") is None:
        raise Exception("virsh not installed")
    
    vms = load_vms()
    vm = next((v for v in vms if v.name == name), None)
    if not vm:
        raise Exception("vm not found")
    
    statuses = parse_virsh_list()
    is_running = statuses.get(name) == "running"
    
    if cpu is not None and cpu != vm.cpu:
            result = subprocess.run(["virsh", "setvcpus", name, str(cpu), "--maximum", "--config"], capture_output=True, text=True)
            if result.returncode != 0:
                log_vm(f"Warning: setvcpus maximum config failed for [{name}]: {result.stderr.strip()}", error=True)
            
            result = subprocess.run(["virsh", "setvcpus", name, str(cpu), "--config"], capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Failed to set CPU config: {result.stderr.strip()}")
            
            if is_running:
                result = subprocess.run(["virsh", "setvcpus", name, str(cpu), "--maximum", "--live"], capture_output=True, text=True)
                if result.returncode != 0:
                    log_vm(f"Warning: live CPU maximum update failed for [{name}]: {result.stderr.strip()}", error=True)
                result = subprocess.run(["virsh", "setvcpus", name, str(cpu), "--live"], capture_output=True, text=True)
                if result.returncode != 0:
                    log_vm(f"Warning: live CPU update failed for [{name}]: {result.stderr.strip()}", error=True)
            vm.cpu = cpu
    
    if memory is not None and memory != vm.memory:
        # Memory in MB, virsh expects KiB
        memory_kib = memory * 1024
        result = subprocess.run(["virsh", "setmaxmem", name, str(memory_kib), "--config"], capture_output=True, text=True)
        if result.returncode != 0:
            log_vm(f"Warning: setmaxmem failed for [{name}]: {result.stderr.strip()}", error=True)
        result = subprocess.run(["virsh", "setmem", name, str(memory_kib), "--config"], capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Failed to set memory: {result.stderr.strip()}")
        if is_running:
            result = subprocess.run(["virsh", "setmem", name, str(memory_kib), "--live"], capture_output=True, text=True)
            if result.returncode != 0:
                log_vm(f"Warning: live memory update failed for [{name}]: {result.stderr.strip()}", error=True)
        vm.memory = memory
    
    if autostart is not None:
        if autostart:
            subprocess.run(["virsh", "autostart", name], capture_output=True)
        else:
            subprocess.run(["virsh", "autostart", name, "--disable"], capture_output=True)
        vm.autostart = autostart
    
    if iso is not None:
        iso_path = os.path.join(iso_dir, iso)
        if not os.path.isfile(iso_path):
            raise Exception("iso not found")
        subprocess.run([
            "virsh", "change-media", name,
            "--path", iso_path,
            "--device", "cdrom",
            "--config", "--update",
        ], capture_output=True)
        vm.iso = iso
    
    if add_disks:
        if storage_path and os.path.isdir(storage_path):
            vms_root = os.path.join(storage_path, "vms")
            base_dir = os.path.join(vms_root, name)
            
            ensure_parent_permissions(vms_root)
            
            if not os.path.exists(vms_root):
                os.makedirs(vms_root, exist_ok=True)
                set_libvirt_permissions(vms_root)
            
            os.makedirs(base_dir, exist_ok=True)
            set_libvirt_permissions(base_dir)
            vm.storage_path = storage_path
        elif vm.storage_path and os.path.isdir(vm.storage_path):
            vms_root = os.path.join(vm.storage_path, "vms")
            base_dir = os.path.join(vms_root, name)
            
            ensure_parent_permissions(vms_root)
            
            if not os.path.exists(vms_root):
                os.makedirs(vms_root, exist_ok=True)
                set_libvirt_permissions(vms_root)
            
            os.makedirs(base_dir, exist_ok=True)
            set_libvirt_permissions(base_dir)
        else:
            base_dir = "/var/lib/libvirt/images"
        
        for disk_cfg in add_disks:
            size = disk_cfg.get("size", 20) if isinstance(disk_cfg, dict) else getattr(disk_cfg, "size", 20)
            fmt = _validate_disk_format(disk_cfg.get("format", "qcow2") if isinstance(disk_cfg, dict) else getattr(disk_cfg, "format", "qcow2"))
            if not size or size <= 0:
                continue
            add_ext = _disk_extension(fmt)
            disk_path = os.path.join(base_dir, f"{name}_{len(vm.disks) + 1}{add_ext}")
            result = subprocess.run(["qemu-img", "create", "-f", fmt, disk_path, f"{size}G"], capture_output=True, text=True)
            if result.returncode == 0:
                set_libvirt_permissions(disk_path)

                # Determine next available virtio device (vda is primary, use vdb, vdc, etc.)
                target_idx = len(vm.disks) + 1  # +1 because vda is disk 1
                target_device = f"vd{chr(ord('a') + target_idx)}"  # vdb, vdc, vdd, etc.

                result = subprocess.run(["virsh", "attach-disk", name, disk_path, target_device,
                                       "--driver", "qemu", "--subdriver", fmt,
                                       "--targetbus", "virtio", "--persistent"],
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    vm.disks.append(disk_path)
                else:
                    log_vm(f"Warning: could not attach disk [{disk_path}] to [{name}]: {result.stderr.strip()}", error=True)
                    if os.path.exists(disk_path):
                        try:
                            os.remove(disk_path)
                        except Exception:
                            pass
    
    if remove_disks:
        for disk_path in remove_disks:
            if disk_path in vm.disks:
                result = subprocess.run(["virsh", "detach-disk", name, disk_path, "--persistent"], capture_output=True, text=True)
                if result.returncode == 0:
                    vm.disks.remove(disk_path)
                    if os.path.exists(disk_path) and disk_path.endswith('.qcow2'):
                        try:
                            os.remove(disk_path)
                        except Exception as e:
                            log_vm(f"Warning: could not delete disk file [{disk_path}]: {e}", error=True)
                else:
                    log_vm(f"Warning: could not detach disk [{disk_path}] from [{name}]: {result.stderr.strip()}", error=True)
    
    if network_mode is not None:
        if network_mode == "nat":
            vm.network_bridge = "virbr0"
            vm.vlan_id = None
        elif network_mode == "bridge":
            if bridge_interface:
                phys_iface = bridge_interface
                if vlan_id:
                    phys_iface = ensure_vlan_interface(bridge_interface, vlan_id)
                actual_bridge = ensure_bridge_for_interface(phys_iface)
                vm.network_bridge = actual_bridge
                vm.vlan_id = vlan_id
            else:
                raise Exception("bridge_interface required for bridge mode")
        elif network_mode == "internal":
            if not network_name:
                raise Exception("network_name required for internal network mode")
            vm.network_bridge = f"network:{network_name}"
            vm.vlan_id = None
        elif network_mode == "unconfigured":
            vm.network_bridge = "unconfigured"
            vm.vlan_id = None
        elif network_mode == "none":
            vm.network_bridge = "none"
            vm.vlan_id = None
    
    save_vms(vms)
    log_vm(f"Updated VM [{name}]")
    return vm

def start_vm(name: str) -> None:
    """Start a virtual machine."""
    if shutil.which("virsh") is None:
        raise Exception("virsh not installed")
    result = subprocess.run(["virsh", "start", name], capture_output=True, text=True)
    if result.returncode != 0:
        log_vm(f"Failed to start VM [{name}]: {result.stderr.strip()}", error=True)
        raise Exception(result.stderr.strip() or "failed to start")
    log_vm(f"Started VM [{name}]")
    notify("vm_start", f"VM '{name}' is now running")

def shutdown_vm(name: str) -> None:
    """Shutdown a virtual machine (hard stop)."""
    if shutil.which("virsh") is None:
        raise Exception("virsh not installed")
    subprocess.run(["virsh", "shutdown", name], capture_output=True, text=True)
    import time
    time.sleep(2)
    result = subprocess.run(["virsh", "destroy", name], capture_output=True, text=True)
    # destroy returns error if VM is already stopped, which is ok
    if result.returncode != 0 and "domain is not running" not in result.stderr.lower():
        log_vm(f"Failed to stop VM [{name}]: {result.stderr.strip()}", error=True)
        raise Exception(result.stderr.strip() or "failed to stop")
    log_vm(f"Stopped VM [{name}]")
    notify("vm_stop", f"VM '{name}' has been shut down")

def delete_vm(name: str) -> None:
    """Delete a virtual machine and remove it from storage."""
    if shutil.which("virsh") is None:
        raise Exception("virsh not installed")
    
    vms = load_vms()
    vm = next((v for v in vms if v.name == name), None)
    
    subprocess.run(["virsh", "destroy", name], capture_output=True)

    # Delete all snapshots before undefining — virsh undefine fails if snapshots exist
    snap_list = subprocess.run(["virsh", "snapshot-list", name, "--name"],
                               capture_output=True, text=True)
    if snap_list.returncode == 0:
        for snap_name in snap_list.stdout.strip().splitlines():
            snap_name = snap_name.strip()
            if snap_name:
                subprocess.run(["virsh", "snapshot-delete", name, snap_name, "--metadata"],
                               capture_output=True)

    result = subprocess.run(["virsh", "undefine", name, "--nvram"], capture_output=True, text=True)
    if result.returncode != 0:
        # Try without --nvram if it fails
        result = subprocess.run(["virsh", "undefine", name], capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(result.stderr.strip() or "failed to delete")
    
    if vm and vm.disks:
        for disk in vm.disks:
            if os.path.exists(disk) and os.path.isfile(disk):
                try:
                    os.remove(disk)
                except Exception as e:
                    log_vm(f"Warning: could not delete disk [{disk}] for VM [{name}]: {e}", error=True)
    
    if vm and vm.cloud_init_iso and os.path.exists(vm.cloud_init_iso):
        try:
            os.remove(vm.cloud_init_iso)
        except Exception as e:
            log_vm(f"Warning: could not delete cloud-init ISO for VM [{name}]: {e}", error=True)
    
    vms = [v for v in load_vms() if v.name != name]
    save_vms(vms)
    log_vm(f"Deleted VM [{name}]")
    notify("vm_delete", f"VM '{name}' has been permanently deleted")

def list_vms_with_status() -> List[VirtualMachine]:
    """List all VMs with their current status from virsh."""
    existing = load_vms()
    statuses = parse_virsh_list()
    
    for vm in existing:
        vm.status = statuses.get(vm.name, vm.status)
        
        if vm.status == "running":
            stats = get_vm_stats(vm.name)
            vm.cpu_usage = stats.get("cpu_usage", 0.0)
            vm.memory_usage = stats.get("memory_usage", 0.0)
        else:
            vm.cpu_usage = 0.0
            vm.memory_usage = 0.0
    
    for idx, vm in enumerate(existing, start=1):
        vm.id = idx
    
    return existing

def clone_vm(source_name: str, new_name: str, storage_path: str | None = None) -> VirtualMachine:
    """Clone an existing virtual machine including its disks.
    
    Args:
        source_name: Name of the VM to clone
        new_name: Name for the new cloned VM
        storage_path: Optional custom storage path for the clone
    """
    if shutil.which("virt-clone") is None:
        raise Exception("virt-clone is not installed. Install libvirt-clients package.")
    
    vms = load_vms()
    source_vm = None
    for vm in vms:
        if vm.name == source_name:
            source_vm = vm
            break
    
    if not source_vm:
        raise Exception(f"Source VM '{source_name}' not found")
    
    for vm in vms:
        if vm.name == new_name:
            raise Exception(f"VM '{new_name}' already exists")
    
    if storage_path:
        ensure_parent_permissions(storage_path)
        vm_storage_dir = os.path.join(storage_path, "vms", new_name)
    else:
        vm_storage_dir = f"/var/lib/libvirt/images/{new_name}"
    
    os.makedirs(vm_storage_dir, exist_ok=True)
    set_libvirt_permissions(vm_storage_dir)
    ensure_parent_permissions(vm_storage_dir)
    
    # virt-clone will automatically copy all disks from the source VM
    cmd = [
        "virt-clone",
        "--original", source_name,
        "--name", new_name,
        "--auto-clone"  # Automatically clone all disks
    ]
    
    if storage_path:
        new_disks = []
        for i, old_disk in enumerate(source_vm.disks):
            disk_name = f"disk{i}.qcow2" if i > 0 else "disk.qcow2"
            new_disk_path = os.path.join(vm_storage_dir, disk_name)
            new_disks.append(new_disk_path)
            cmd.extend(["--file", new_disk_path])
        
        # Remove --auto-clone if we specify files manually
        cmd.remove("--auto-clone")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        log_vm(f"Cloned VM [{source_name}] → [{new_name}]")
    except subprocess.CalledProcessError as e:
        log_vm(f"Failed to clone VM [{source_name}] → [{new_name}]: {e.stderr.strip()}", error=True)
        raise Exception(f"Failed to clone VM: {e.stderr}")
    
    new_disks = []
    domblklist = subprocess.run(["virsh", "domblklist", new_name], capture_output=True, text=True)
    if domblklist.returncode == 0:
        for line in domblklist.stdout.splitlines()[2:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1].endswith('.qcow2'):
                new_disks.append(parts[1])
    
    new_vm = VirtualMachine(
        id=len(vms) + 1,
        name=new_name,
        status="stopped",
        cpu=source_vm.cpu,
        memory=source_vm.memory,
        iso=source_vm.iso,
        disks=new_disks,
        created=datetime.now().strftime("%Y-%m-%d"),
        autostart=False,  # Don't autostart clones by default
        network_bridge=source_vm.network_bridge,
        graphics=source_vm.graphics,
        storage_path=storage_path
    )
    
    vms.append(new_vm)
    save_vms(vms)
    
    return new_vm


# ──────────────────────────────────────────────
# Snapshot management
# ──────────────────────────────────────────────

def list_snapshots(vm_name: str) -> List[dict]:
    """List all snapshots for a VM."""
    if shutil.which("virsh") is None:
        raise Exception("virsh not installed")
    result = subprocess.run(["virsh", "snapshot-list", vm_name, "--name"],
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(result.stderr.strip() or "Failed to list snapshots")
    names = [n.strip() for n in result.stdout.strip().splitlines() if n.strip()]
    snapshots = []
    for sname in names:
        info_result = subprocess.run(["virsh", "snapshot-info", vm_name, sname],
                                     capture_output=True, text=True)
        info: dict = {}
        if info_result.returncode == 0:
            for line in info_result.stdout.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    info[k.strip().lower().replace(" ", "_")] = v.strip()
        snapshots.append({
            "name": sname,
            "created": info.get("creation_time", ""),
            "state": info.get("state", ""),
            "description": info.get("description", ""),
        })
    return snapshots


def create_snapshot(vm_name: str, snapshot_name: str, description: str = "") -> dict:
    """Create an internal snapshot (requires qcow2 disks).
    Works for both running and stopped VMs."""
    if shutil.which("virsh") is None:
        raise Exception("virsh not installed")
    args = ["virsh", "snapshot-create-as", vm_name, snapshot_name]
    if description:
        args.extend(["--description", description])
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        log_vm(f"Failed to create snapshot [{snapshot_name}] on VM [{vm_name}]: {result.stderr.strip()}", error=True)
        raise Exception(result.stderr.strip() or "Failed to create snapshot")
    log_vm(f"Created snapshot [{snapshot_name}] on VM [{vm_name}]")
    return {"name": snapshot_name, "description": description}


def delete_snapshot(vm_name: str, snapshot_name: str) -> None:
    """Delete a snapshot."""
    if shutil.which("virsh") is None:
        raise Exception("virsh not installed")
    result = subprocess.run(["virsh", "snapshot-delete", vm_name, snapshot_name],
                            capture_output=True, text=True)
    if result.returncode != 0:
        log_vm(f"Failed to delete snapshot [{snapshot_name}] from VM [{vm_name}]: {result.stderr.strip()}", error=True)
        raise Exception(result.stderr.strip() or "Failed to delete snapshot")
    log_vm(f"Deleted snapshot [{snapshot_name}] from VM [{vm_name}]")


def restore_snapshot(vm_name: str, snapshot_name: str) -> None:
    """Revert a VM to a snapshot. Forces shutdown if VM is running."""
    if shutil.which("virsh") is None:
        raise Exception("virsh not installed")
    result = subprocess.run(
        ["virsh", "snapshot-revert", vm_name, snapshot_name, "--force"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        log_vm(f"Failed to restore snapshot [{snapshot_name}] on VM [{vm_name}]: {result.stderr.strip()}", error=True)
        raise Exception(result.stderr.strip() or "Failed to restore snapshot")
    log_vm(f"Restored VM [{vm_name}] to snapshot [{snapshot_name}]")


# ──────────────────────────────────────────────
# OVA/OVF Export
# ──────────────────────────────────────────────

EXPORT_DIR = "/etc/upcode-harbor/exports"


def _build_ovf(vm_name: str, cpu: int, memory_mb: int, disks: list[dict]) -> str:
    """Generate a minimal OVF 1.0 descriptor for the given VM configuration.

    Args:
        vm_name: VM name (used as OVF display name)
        cpu: vCPU count
        memory_mb: RAM in MiB
        disks: list of dicts with keys 'id', 'href', 'capacity_bytes'
    """
    import xml.etree.ElementTree as ET

    ns_ovf = "http://schemas.dmtf.org/ovf/envelope/1"
    ns_rasd = "http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData"
    ns_vssd = "http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_VirtualSystemSettingData"
    ns_xsi = "http://www.w3.org/2001/XMLSchema-instance"

    ET.register_namespace("ovf", ns_ovf)
    ET.register_namespace("rasd", ns_rasd)
    ET.register_namespace("vssd", ns_vssd)
    ET.register_namespace("xsi", ns_xsi)

    def _q(ns: str, tag: str) -> str:
        return f"{{{ns}}}{tag}"

    envelope = ET.Element(_q(ns_ovf, "Envelope"))
    envelope.set("xmlns", ns_ovf)
    envelope.set(_q(ns_xsi, "schemaLocation"), f"{ns_ovf} dsp8023.xsd")

    # References
    refs = ET.SubElement(envelope, _q(ns_ovf, "References"))
    for d in disks:
        f_el = ET.SubElement(refs, _q(ns_ovf, "File"))
        f_el.set(_q(ns_ovf, "id"), d["id"])
        f_el.set(_q(ns_ovf, "href"), d["href"])

    # DiskSection
    disk_section = ET.SubElement(envelope, _q(ns_ovf, "DiskSection"))
    ET.SubElement(disk_section, _q(ns_ovf, "Info")).text = "Virtual disk information"
    for d in disks:
        disk_el = ET.SubElement(disk_section, _q(ns_ovf, "Disk"))
        disk_el.set(_q(ns_ovf, "diskId"), d["id"])
        disk_el.set(_q(ns_ovf, "fileRef"), d["id"])
        disk_el.set(_q(ns_ovf, "capacity"), str(d["capacity_bytes"]))
        disk_el.set(_q(ns_ovf, "capacityAllocationUnits"), "byte")
        disk_el.set(_q(ns_ovf, "format"), "http://www.vmware.com/interfaces/specifications/vmdk.html#streamOptimized")
        disk_el.set(_q(ns_ovf, "populatedSize"), str(d.get("populated_bytes", d["capacity_bytes"])))

    # NetworkSection
    net_section = ET.SubElement(envelope, _q(ns_ovf, "NetworkSection"))
    ET.SubElement(net_section, _q(ns_ovf, "Info")).text = "Logical networks"
    net_el = ET.SubElement(net_section, _q(ns_ovf, "Network"))
    net_el.set(_q(ns_ovf, "name"), "VM Network")
    ET.SubElement(net_el, _q(ns_ovf, "Description")).text = "Default VM Network"

    # VirtualSystem
    vs = ET.SubElement(envelope, _q(ns_ovf, "VirtualSystem"))
    vs.set(_q(ns_ovf, "id"), vm_name)
    ET.SubElement(vs, _q(ns_ovf, "Info")).text = f"Virtual machine {vm_name}"
    ET.SubElement(vs, _q(ns_ovf, "Name")).text = vm_name

    # OperatingSystemSection
    os_section = ET.SubElement(vs, _q(ns_ovf, "OperatingSystemSection"))
    os_section.set(_q(ns_ovf, "id"), "1")
    ET.SubElement(os_section, _q(ns_ovf, "Info")).text = "Guest operating system"
    ET.SubElement(os_section, _q(ns_ovf, "Description")).text = "Other Linux (64-bit)"

    # VirtualHardwareSection
    hw = ET.SubElement(vs, _q(ns_ovf, "VirtualHardwareSection"))
    ET.SubElement(hw, _q(ns_ovf, "Info")).text = "Virtual hardware requirements"

    system = ET.SubElement(hw, _q(ns_ovf, "System"))
    ET.SubElement(system, _q(ns_vssd, "ElementName")).text = "Virtual Hardware Family"
    ET.SubElement(system, _q(ns_vssd, "InstanceID")).text = "0"
    ET.SubElement(system, _q(ns_vssd, "VirtualSystemIdentifier")).text = vm_name
    ET.SubElement(system, _q(ns_vssd, "VirtualSystemType")).text = "vmx-13"

    # CPU
    cpu_item = ET.SubElement(hw, _q(ns_ovf, "Item"))
    ET.SubElement(cpu_item, _q(ns_rasd, "AllocationUnits")).text = "hertz * 10^6"
    ET.SubElement(cpu_item, _q(ns_rasd, "Description")).text = "Number of virtual CPUs"
    ET.SubElement(cpu_item, _q(ns_rasd, "ElementName")).text = f"{cpu} virtual CPU(s)"
    ET.SubElement(cpu_item, _q(ns_rasd, "InstanceID")).text = "1"
    ET.SubElement(cpu_item, _q(ns_rasd, "ResourceType")).text = "3"
    ET.SubElement(cpu_item, _q(ns_rasd, "VirtualQuantity")).text = str(cpu)

    # Memory
    mem_item = ET.SubElement(hw, _q(ns_ovf, "Item"))
    ET.SubElement(mem_item, _q(ns_rasd, "AllocationUnits")).text = "byte * 2^20"
    ET.SubElement(mem_item, _q(ns_rasd, "Description")).text = "Memory Size"
    ET.SubElement(mem_item, _q(ns_rasd, "ElementName")).text = f"{memory_mb} MB of memory"
    ET.SubElement(mem_item, _q(ns_rasd, "InstanceID")).text = "2"
    ET.SubElement(mem_item, _q(ns_rasd, "ResourceType")).text = "4"
    ET.SubElement(mem_item, _q(ns_rasd, "VirtualQuantity")).text = str(memory_mb)

    # Network adapter
    nic_item = ET.SubElement(hw, _q(ns_ovf, "Item"))
    ET.SubElement(nic_item, _q(ns_rasd, "AutomaticAllocation")).text = "true"
    ET.SubElement(nic_item, _q(ns_rasd, "Connection")).text = "VM Network"
    ET.SubElement(nic_item, _q(ns_rasd, "Description")).text = "VirtIO Ethernet Adapter"
    ET.SubElement(nic_item, _q(ns_rasd, "ElementName")).text = "Network adapter 1"
    ET.SubElement(nic_item, _q(ns_rasd, "InstanceID")).text = "3"
    ET.SubElement(nic_item, _q(ns_rasd, "ResourceSubType")).text = "VirtIO"
    ET.SubElement(nic_item, _q(ns_rasd, "ResourceType")).text = "10"

    # Disk items (SCSI controller + disks)
    ctrl_item = ET.SubElement(hw, _q(ns_ovf, "Item"))
    ET.SubElement(ctrl_item, _q(ns_rasd, "Address")).text = "0"
    ET.SubElement(ctrl_item, _q(ns_rasd, "Description")).text = "SCSI Controller"
    ET.SubElement(ctrl_item, _q(ns_rasd, "ElementName")).text = "SCSI controller 0"
    ET.SubElement(ctrl_item, _q(ns_rasd, "InstanceID")).text = "4"
    ET.SubElement(ctrl_item, _q(ns_rasd, "ResourceSubType")).text = "lsilogic"
    ET.SubElement(ctrl_item, _q(ns_rasd, "ResourceType")).text = "6"

    for idx, d in enumerate(disks):
        disk_item = ET.SubElement(hw, _q(ns_ovf, "Item"))
        ET.SubElement(disk_item, _q(ns_rasd, "AddressOnParent")).text = str(idx)
        ET.SubElement(disk_item, _q(ns_rasd, "ElementName")).text = f"Hard disk {idx + 1}"
        ET.SubElement(disk_item, _q(ns_rasd, "HostResource")).text = f"ovf:/disk/{d['id']}"
        ET.SubElement(disk_item, _q(ns_rasd, "InstanceID")).text = str(10 + idx)
        ET.SubElement(disk_item, _q(ns_rasd, "Parent")).text = "4"
        ET.SubElement(disk_item, _q(ns_rasd, "ResourceType")).text = "17"

    return ET.tostring(envelope, encoding="unicode", xml_declaration=False)


def export_vm_ova(name: str, export_format: str = "ova") -> str:
    """Export a virtual machine as OVA or OVF package.

    The VM must be stopped before export. The resulting file is placed in
    EXPORT_DIR and its path is returned.

    Args:
        name: Name of the VM to export.
        export_format: 'ova' (single archive) or 'ovf' (directory with OVF+VMDKs).

    Returns:
        Absolute path to the exported .ova file or the .ovf descriptor file.
    """
    if shutil.which("virsh") is None:
        raise Exception("virsh is not installed")
    if shutil.which("qemu-img") is None:
        raise Exception("qemu-img is not installed")

    export_format = export_format.lower()
    if export_format not in ("ova", "ovf"):
        raise ValueError("export_format must be 'ova' or 'ovf'")

    # Ensure VM exists and is stopped
    statuses = parse_virsh_list()
    if name not in statuses and name not in [v.name for v in load_vms()]:
        raise Exception(f"VM '{name}' not found")
    if statuses.get(name) == "running":
        raise Exception("VM must be stopped before export. Please shut it down first.")

    vms = load_vms()
    vm = next((v for v in vms if v.name == name), None)
    if not vm:
        raise Exception(f"VM '{name}' not found in registry")

    # Get actual disk paths from libvirt (excludes CD-ROMs)
    blklist = subprocess.run(
        ["virsh", "domblklist", name, "--details"],
        capture_output=True, text=True,
    )
    source_disks: list[str] = []
    if blklist.returncode == 0:
        for line in blklist.stdout.splitlines()[2:]:
            parts = line.split()
            # parts: type  device  target  source
            if len(parts) >= 4 and parts[0] == "file" and parts[1] == "disk":
                src = parts[3]
                if os.path.isfile(src):
                    source_disks.append(src)
    # Fallback: use stored disk list
    if not source_disks:
        source_disks = [d for d in (vm.disks or []) if os.path.isfile(d)]
    if not source_disks:
        raise Exception("No disk images found for this VM")

    ensure_config_directory(EXPORT_DIR)
    work_dir = tempfile.mkdtemp(prefix=f"ovf_export_{name}_", dir=EXPORT_DIR)

    try:
        disk_meta: list[dict] = []
        for idx, src_path in enumerate(source_disks):
            disk_id = f"disk{idx}"
            vmdk_name = f"{name}_disk{idx}.vmdk"
            vmdk_path = os.path.join(work_dir, vmdk_name)

            log_vm(f"Converting disk [{src_path}] → [{vmdk_path}] (streamOptimized)")
            r = subprocess.run(
                ["qemu-img", "convert", "-p", "-f", "qcow2", "-O", "vmdk",
                 "-o", "subformat=streamOptimized", src_path, vmdk_path],
                capture_output=True, text=True,
            )
            if r.returncode != 0:
                # Retry without subformat (older qemu-img versions)
                r2 = subprocess.run(
                    ["qemu-img", "convert", "-f", "qcow2", "-O", "vmdk", src_path, vmdk_path],
                    capture_output=True, text=True,
                )
                if r2.returncode != 0:
                    raise Exception(f"Disk conversion failed: {r2.stderr.strip()}")

            capacity_bytes = os.path.getsize(src_path)
            vmdk_size = os.path.getsize(vmdk_path)
            disk_meta.append({
                "id": disk_id,
                "href": vmdk_name,
                "capacity_bytes": capacity_bytes,
                "populated_bytes": vmdk_size,
            })

        # Generate OVF descriptor
        ovf_xml = _build_ovf(name, vm.cpu, vm.memory, disk_meta)
        ovf_path = os.path.join(work_dir, f"{name}.ovf")
        with open(ovf_path, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(ovf_xml)

        # Generate simple MF (manifest) with SHA256
        import hashlib
        mf_path = os.path.join(work_dir, f"{name}.mf")
        with open(mf_path, "w") as mf:
            for entry_path in [ovf_path] + [os.path.join(work_dir, d["href"]) for d in disk_meta]:
                h = hashlib.sha256()
                with open(entry_path, "rb") as fp:
                    for chunk in iter(lambda: fp.read(1 << 20), b""):
                        h.update(chunk)
                mf.write(f"SHA256({os.path.basename(entry_path)})= {h.hexdigest()}\n")

        if export_format == "ova":
            import tarfile
            ova_path = os.path.join(EXPORT_DIR, f"{name}.ova")
            # OVA spec: OVF first, then MF, then disk images
            with tarfile.open(ova_path, "w") as tar:
                tar.add(ovf_path, arcname=f"{name}.ovf")
                tar.add(mf_path, arcname=f"{name}.mf")
                for d in disk_meta:
                    tar.add(os.path.join(work_dir, d["href"]), arcname=d["href"])
            log_vm(f"Exported VM [{name}] as OVA → [{ova_path}]")
            notify("vm_export", f"VM '{name}' exported as OVA ({os.path.getsize(ova_path) // (1024*1024)} MB)")
            return ova_path
        else:
            # OVF: move the work_dir contents to a named directory
            out_dir = os.path.join(EXPORT_DIR, f"{name}_ovf")
            if os.path.exists(out_dir):
                shutil.rmtree(out_dir)
            shutil.move(work_dir, out_dir)
            log_vm(f"Exported VM [{name}] as OVF → [{out_dir}]")
            notify("vm_export", f"VM '{name}' exported as OVF package")
            return os.path.join(out_dir, f"{name}.ovf")
    except Exception:
        # Cleanup temp dir on error
        if os.path.isdir(work_dir):
            try:
                shutil.rmtree(work_dir)
            except Exception:
                pass
        raise


# ──────────────────────────────────────────────
# OVA/OVF Import
# ──────────────────────────────────────────────

IMPORT_DIR = "/etc/upcode-harbor/imports"


def _parse_ovf(ovf_path: str) -> dict:
    """Parse an OVF descriptor and extract VM configuration.

    Returns a dict with keys: cpu, memory_mb, disk_hrefs (list of filenames).
    Falls back to safe defaults when elements are missing.
    """
    import xml.etree.ElementTree as ET

    tree = ET.parse(ovf_path)
    root = tree.getroot()

    # Strip namespace from tag for matching
    def _tag(el) -> str:
        return el.tag.split("}")[-1] if "}" in el.tag else el.tag

    cpu = 1
    memory_mb = 512
    disk_hrefs: list[str] = []

    # Collect File hrefs (actual disk file names referenced in References)
    ns_map: dict[str, str] = {}
    for prefix, uri in [
        ("ovf", "http://schemas.dmtf.org/ovf/envelope/1"),
        ("rasd", "http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData"),
    ]:
        ns_map[prefix] = uri

    # Iterate all elements to find References/File and Item entries
    for el in root.iter():
        tag = _tag(el)

        if tag == "File":
            href = None
            for attr_name, attr_val in el.attrib.items():
                if attr_name.split("}")[-1] == "href":
                    href = attr_val
                    break
            if href and (href.endswith(".vmdk") or href.endswith(".img") or href.endswith(".qcow2")):
                disk_hrefs.append(href)

        if tag == "Item":
            resource_type = None
            quantity = None
            allocation_units = None
            for child in el:
                child_tag = _tag(child)
                if child_tag == "ResourceType":
                    resource_type = child.text.strip() if child.text else None
                elif child_tag == "VirtualQuantity":
                    quantity = child.text.strip() if child.text else None
                elif child_tag == "AllocationUnits":
                    allocation_units = (child.text or "").strip().lower()

            if resource_type == "3" and quantity:  # CPU
                try:
                    cpu = int(quantity)
                except ValueError:
                    pass
            elif resource_type == "4" and quantity:  # Memory
                try:
                    raw = int(quantity)
                    # Convert to MB if units indicate bytes or GiB
                    if "byte * 2^30" in allocation_units or "gib" in allocation_units:
                        memory_mb = raw * 1024
                    elif "byte * 2^20" in allocation_units or "mib" in allocation_units or "mb" in allocation_units:
                        memory_mb = raw
                    elif "byte * 2^10" in allocation_units or "kib" in allocation_units:
                        memory_mb = max(512, raw // 1024)
                    elif "byte" in allocation_units and "^" not in allocation_units:
                        memory_mb = max(512, raw // (1024 * 1024))
                    else:
                        # Assume MB (most common OVF default)
                        memory_mb = raw
                except ValueError:
                    pass

    return {"cpu": cpu, "memory_mb": memory_mb, "disk_hrefs": disk_hrefs}


def import_vm_ova(
    source_path: str,
    name: str,
    network_mode: str = "nat",
    bridge_interface: str | None = None,
    vlan_id: int | None = None,
    network_name: str | None = None,
    autostart: bool = False,
    storage_path: str | None = None,
) -> VirtualMachine:
    """Import a virtual machine from an OVA or OVF file.

    Supports:
    - OVA archives (.ova) – single TAR containing OVF + disks
    - OVF descriptors (.ovf) – together with VMDK/qcow2 disk files in the same directory

    The disks are converted to qcow2 via ``qemu-img`` and registered with libvirt.

    Args:
        source_path: Absolute path to the .ova or .ovf file on the server.
        name: Desired VM name (must be unique).
        network_mode: "nat" | "bridge" | "none" | "unconfigured"
        bridge_interface: Physical interface name required for bridge mode.
        autostart: Whether the VM should autostart on host boot.
        storage_path: Optional mounted drive path; disks go to {storage_path}/vms/{name}/.

    Returns:
        The newly created VirtualMachine record.
    """
    for tool in ("virsh", "virt-install", "qemu-img"):
        if shutil.which(tool) is None:
            raise Exception(f"{tool} is not installed")

    # Name collision check
    existing = load_vms()
    if any(v.name == name for v in existing):
        raise Exception(f"A VM named '{name}' already exists")

    ensure_config_directory(IMPORT_DIR)
    work_dir = tempfile.mkdtemp(prefix=f"ovf_import_{name}_", dir=IMPORT_DIR)

    try:
        ext = os.path.splitext(source_path)[1].lower()

        if ext == ".ova":
            import tarfile
            log_vm(f"Extracting OVA [{source_path}] → [{work_dir}]")
            with tarfile.open(source_path, "r") as tar:
                # Security: reject paths with ".." or absolute paths
                for member in tar.getmembers():
                    if os.path.isabs(member.name) or ".." in member.name:
                        raise Exception(f"Unsafe path in OVA archive: {member.name}")
                tar.extractall(work_dir)
            # Locate .ovf inside extracted directory
            ovf_files = [f for f in os.listdir(work_dir) if f.endswith(".ovf")]
            if not ovf_files:
                raise Exception("No OVF descriptor found inside OVA archive")
            ovf_path = os.path.join(work_dir, ovf_files[0])

        elif ext == ".ovf":
            # OVF descriptor passed directly – disk files must be in the same directory
            ovf_path = source_path
            ovf_dir = os.path.dirname(source_path)
            # Copy relevant files into work_dir so we work in a controlled location
            for f in os.listdir(ovf_dir):
                if f.endswith((".ovf", ".vmdk", ".img", ".qcow2", ".mf")):
                    shutil.copy2(os.path.join(ovf_dir, f), os.path.join(work_dir, f))
            ovf_path = os.path.join(work_dir, os.path.basename(source_path))
        else:
            raise Exception("Unsupported file type: must be .ova or .ovf")

        # Parse OVF to extract configuration
        config = _parse_ovf(ovf_path)
        cpu = max(1, config["cpu"])
        memory_mb = max(256, config["memory_mb"])
        disk_hrefs = config["disk_hrefs"]

        log_vm(f"OVF parsed: CPU={cpu}, RAM={memory_mb} MB, disks={disk_hrefs}")

        if not disk_hrefs:
            raise Exception("OVF contains no disk references – cannot import")

        # Destination directory for converted qcow2 disks
        if storage_path and os.path.isdir(storage_path):
            vms_root = os.path.join(storage_path, "vms")
            dest_dir = os.path.join(vms_root, name)
            ensure_parent_permissions(vms_root)
            os.makedirs(dest_dir, exist_ok=True)
            set_libvirt_permissions(dest_dir)
        else:
            dest_dir = os.path.join("/var/lib/libvirt/images", name)
            os.makedirs(dest_dir, exist_ok=True)

        # Convert each disk to qcow2
        qcow2_paths: list[str] = []
        for idx, href in enumerate(disk_hrefs):
            src_disk = os.path.join(work_dir, os.path.basename(href))
            if not os.path.isfile(src_disk):
                raise Exception(f"Disk file not found in archive: {href}")

            dest_disk = os.path.join(dest_dir, f"{name}_{idx + 1}.qcow2")
            log_vm(f"Converting disk [{src_disk}] → [{dest_disk}]")

            # Detect source format
            probe = subprocess.run(
                ["qemu-img", "info", "--output=json", src_disk],
                capture_output=True, text=True,
            )
            src_fmt = "vmdk"
            if probe.returncode == 0:
                import json as _json
                try:
                    src_fmt = _json.loads(probe.stdout).get("format", "vmdk")
                except Exception:
                    pass

            r = subprocess.run(
                ["qemu-img", "convert", "-f", src_fmt, "-O", "qcow2", src_disk, dest_disk],
                capture_output=True, text=True,
            )
            if r.returncode != 0:
                raise Exception(f"Disk conversion failed: {r.stderr.strip()}")

            set_libvirt_permissions(dest_disk)
            qcow2_paths.append(dest_disk)

        # Build virt-install command
        network_bridge = "virbr0"
        if network_mode == "nat":
            network_args = ["--network", "network=default"]
        elif network_mode == "bridge":
            if not bridge_interface:
                raise Exception("bridge_interface required for bridge mode")
            phys_iface = bridge_interface
            if vlan_id:
                phys_iface = ensure_vlan_interface(bridge_interface, vlan_id)
            actual_bridge = ensure_bridge_for_interface(phys_iface)
            network_args = ["--network", f"bridge={actual_bridge}"]
            network_bridge = actual_bridge
        elif network_mode == "internal":
            if not network_name:
                raise Exception("network_name required for internal network mode")
            network_args = ["--network", f"network={network_name}"]
            network_bridge = f"network:{network_name}"
        elif network_mode == "unconfigured":
            network_args = ["--network", "type=ethernet,model=virtio"]
            network_bridge = "unconfigured"
        else:
            network_args = ["--network", "none"]
            network_bridge = "none"

        disk_args: list[str] = []
        for qpath in qcow2_paths:
            disk_args += ["--disk", f"path={qpath},format=qcow2"]

        cmd = [
            "virt-install",
            "--name", name,
            "--ram", str(memory_mb),
            "--vcpus", str(cpu),
            *disk_args,
            "--os-variant", "generic",
            *network_args,
            "--graphics", "vnc",
            "--hvm",
            "--noautoconsole",
            "--import",   # Skip OS installation, boot from the first disk
        ]

        log_vm(f"Registering imported VM [{name}] with libvirt")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(result.stderr.strip() or "virt-install failed")

        if autostart:
            subprocess.run(["virsh", "autostart", name], capture_output=True)

        vms = load_vms()
        vm = VirtualMachine(
            id=len(vms) + 1,
            name=name,
            status="stopped",
            cpu=cpu,
            memory=memory_mb,
            iso="",
            disks=qcow2_paths,
            created=datetime.utcnow().date().isoformat(),
            autostart=autostart,
            network_bridge=network_bridge,
            vlan_id=vlan_id if network_mode == "bridge" else None,
            storage_path=storage_path,
        )
        vms.append(vm)
        save_vms(vms)

        log_vm(f"Imported VM [{name}] (CPU: {cpu}, RAM: {memory_mb} MB, disks: {len(qcow2_paths)})")
        notify("vm_import", f"VM '{name}' imported successfully | CPU: {cpu} | RAM: {memory_mb} MB | Disks: {len(qcow2_paths)}")
        return vm

    finally:
        if os.path.isdir(work_dir):
            try:
                shutil.rmtree(work_dir)
            except Exception:
                pass
