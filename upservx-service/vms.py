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
from models import VirtualMachine
from upservx_logger import log_vm

import time

VM_FILE = "/etc/upservx/vms.json"

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
    with open(VM_FILE, "w") as f:
        json.dump([vm.dict() for vm in vms], f)

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
              network_mode: str = "nat", bridge_interface: str | None = None, autostart: bool = False,
              cloud_init: str | None = None, storage_path: str | None = None) -> VirtualMachine:
    """Create a new virtual machine using virt-install.

    Supports optional cloud-init user-data (string). If `cloud_init` is provided
    a small seed ISO will be created and attached as a CD-ROM.
    network_mode: "nat" (virbr0), "bridge" (direct to physical), or "none" (no network)
    bridge_interface: physical interface name for bridge mode (e.g. "wlp3s0", "enp0s31f6")
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
            
            actual_bridge = ensure_bridge_for_interface(bridge_interface)
            network_args = ["--network", f"bridge={actual_bridge}"]
            network_bridge = actual_bridge
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
            cloud_init_iso=seed_iso_path,
            storage_path=storage_path,
        )
        log_vm(f"Created VM [{name}] (CPU: {cpu}, Memory: {memory} MB, Network: {network_bridge})")
        vms.append(vm)
        save_vms(vms)
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
        elif network_mode == "bridge":
            if bridge_interface:
                vm.network_bridge = bridge_interface
            else:
                raise Exception("bridge_interface required for bridge mode")
        elif network_mode == "unconfigured":
            vm.network_bridge = "unconfigured"
        elif network_mode == "none":
            vm.network_bridge = "none"
    
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
