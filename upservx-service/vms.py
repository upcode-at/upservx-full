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


import time


VM_FILE = "/etc/upservx/vms.json"


def set_libvirt_permissions(path: str) -> None:
    """Set ownership and permissions for libvirt-qemu user."""
    try:
        # Get libvirt-qemu user and group IDs
        uid = pwd.getpwnam("libvirt-qemu").pw_uid
        gid = grp.getgrnam("libvirt-qemu").gr_gid
        
        # Set ownership
        os.chown(path, uid, gid)
        
        # Set permissions: 755 for directories, 644 for files
        if os.path.isdir(path):
            os.chmod(path, 0o755)
        else:
            os.chmod(path, 0o644)
    except (KeyError, PermissionError) as e:
        print(f"Warning: Could not set libvirt permissions on {path}: {e}")


def ensure_parent_permissions(path: str) -> None:
    """Ensure all parent directories are accessible (executable) for libvirt-qemu."""
    try:
        # Get libvirt-qemu group ID
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
                print(f"Warning: Could not set permissions on parent directory {current}: {e}")
                break
            
            parent = os.path.dirname(current)
            if parent == current:  # Reached root
                break
            current = parent
    except (KeyError, PermissionError) as e:
        print(f"Warning: Could not ensure parent permissions for {path}: {e}")


def ensure_bridge_for_interface(interface: str) -> str:
    """Ensure a Linux bridge exists for the given physical interface.
    Returns the bridge name (e.g., br0).
    Transfers IP configuration from interface to bridge.
    """
    bridge_name = f"br-{interface}"
    
    # Check if bridge already exists
    result = subprocess.run(["ip", "link", "show", bridge_name], capture_output=True, text=True)
    if result.returncode == 0:
        # Bridge already exists
        return bridge_name
    
    try:
        # Get current IP configuration of physical interface
        ip_info = subprocess.run(["ip", "addr", "show", interface], capture_output=True, text=True, check=True)
        
        # Extract IP addresses (both IPv4 and IPv6)
        import re
        ip_addresses = []
        for line in ip_info.stdout.splitlines():
            match = re.search(r'inet6?\s+([^\s]+)', line)
            if match:
                ip_addresses.append(match.group(1))
        
        # Get current default gateway
        route_info = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True)
        gateway = None
        for line in route_info.stdout.splitlines():
            if f"dev {interface}" in line:
                match = re.search(r'via\s+([^\s]+)', line)
                if match:
                    gateway = match.group(1)
        
        # Create bridge
        subprocess.run(["ip", "link", "add", "name", bridge_name, "type", "bridge"], check=True, capture_output=True)
        
        # Remove IP addresses from physical interface
        for ip_addr in ip_addresses:
            subprocess.run(["ip", "addr", "del", ip_addr, "dev", interface], capture_output=True)
        
        # Add physical interface to bridge (must be done before bringing bridge up)
        subprocess.run(["ip", "link", "set", interface, "master", bridge_name], check=True, capture_output=True)
        
        # Bring bridge up
        subprocess.run(["ip", "link", "set", bridge_name, "up"], check=True, capture_output=True)
        
        # Bring physical interface up
        subprocess.run(["ip", "link", "set", interface, "up"], check=True, capture_output=True)
        
        # Assign IP addresses to bridge
        for ip_addr in ip_addresses:
            subprocess.run(["ip", "addr", "add", ip_addr, "dev", bridge_name], capture_output=True)
        
        # Restore default gateway if it existed
        if gateway:
            subprocess.run(["ip", "route", "add", "default", "via", gateway, "dev", bridge_name], capture_output=True)
        
        print(f"Created bridge {bridge_name} for interface {interface} with IP configuration transferred")
        return bridge_name
    except subprocess.CalledProcessError as e:
        print(f"Warning: Could not create bridge for {interface}: {e}")
        # Fallback to direct interface
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
            # Normalize status to English
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
        # Get memory stats using dommemstat
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
            
            # Calculate memory usage with available data
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
        
        # Get CPU usage by measuring CPU time difference
        # Find qemu process PID
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
                # First measurement
                with open(f"/proc/{pid}/stat", "r") as f:
                    stat1 = f.read().split()
                    utime1 = int(stat1[13])
                    stime1 = int(stat1[14])
                
                with open("/proc/stat", "r") as f:
                    cpu_line1 = f.readline().split()
                    cpu_total1 = sum(int(x) for x in cpu_line1[1:])
                
                # Small delay
                time.sleep(0.1)
                
                # Second measurement
                with open(f"/proc/{pid}/stat", "r") as f:
                    stat2 = f.read().split()
                    utime2 = int(stat2[13])
                    stime2 = int(stat2[14])
                
                with open("/proc/stat", "r") as f:
                    cpu_line2 = f.readline().split()
                    cpu_total2 = sum(int(x) for x in cpu_line2[1:])
                
                # Calculate CPU usage percentage
                process_time = (utime2 + stime2) - (utime1 + stime1)
                total_time = cpu_total2 - cpu_total1
                
                if total_time > 0:
                    cpu_usage = (process_time / total_time) * 100
                    stats["cpu_usage"] = round(cpu_usage, 1)
                    
            except (FileNotFoundError, ValueError, IndexError, ZeroDivisionError):
                pass
        
    except (subprocess.TimeoutExpired, Exception) as e:
        print(f"Warning: Could not get stats for VM {name}: {e}")
    
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


def create_vm(name: str, cpu: int, memory: int, iso: str, disks: List[int], iso_dir: str,
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

    # Determine base directory for VM disks
    if storage_path and os.path.isdir(storage_path):
        # Use custom storage path with vms subdirectory
        vms_root = os.path.join(storage_path, "vms")
        base_dir = os.path.join(vms_root, name)
        
        # Ensure parent directories are accessible for libvirt-qemu
        ensure_parent_permissions(vms_root)
        
        # Create vms root directory if it doesn't exist
        if not os.path.exists(vms_root):
            os.makedirs(vms_root, exist_ok=True)
            set_libvirt_permissions(vms_root)
        
        # Create VM directory
        os.makedirs(base_dir, exist_ok=True)
        set_libvirt_permissions(base_dir)
    else:
        # Use default libvirt images directory
        base_dir = "/var/lib/libvirt/images"

    disk_args = []
    disk_paths = []
    for idx, size in enumerate(disks or [20], start=1):
        disk_path = os.path.join(base_dir, f"{name}_{idx}.qcow2")
        disk_paths.append(disk_path)
        r = subprocess.run(["qemu-img", "create", "-f", "qcow2", disk_path, f"{size}G"], capture_output=True, text=True)
        if r.returncode != 0:
            raise Exception(r.stderr.strip() or "failed to create disk")
        # Set correct permissions for libvirt-qemu
        set_libvirt_permissions(disk_path)
        disk_args.extend(["--disk", f"path={disk_path},size={size}"])

    seed_iso_path = None
    tempdir = None
    try:
        if cloud_init:
            # create cloud-init seed ISO
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

            # Set correct permissions for libvirt-qemu
            set_libvirt_permissions(seed_iso_path)

            # attach as CD-ROM
            disk_args.extend(["--disk", f"path={seed_iso_path},device=cdrom"])

        # Configure network based on mode
        network_args = []
        network_bridge = "virbr0"  # default for storage
        if network_mode == "nat":
            network_args = ["--network", "network=default"]
            network_bridge = "virbr0"
        elif network_mode == "bridge":
            # Create/use Linux bridge for true bridged networking
            if not bridge_interface:
                raise Exception("bridge_interface required for bridge mode")
            
            # Ensure bridge exists for the interface
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
            # Attach ISO as persistent CDROM and set boot order
            cmd.extend([
                "--disk", f"path={iso_path},device=cdrom,readonly=on",
                "--boot", "cdrom,hd"
            ])
        else:
            # No ISO, boot from HD
            cmd.extend(["--boot", "hd"])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(result.stderr.strip() or "failed to create")

        # optionally set autostart
        if autostart:
            r2 = subprocess.run(["virsh", "autostart", name], capture_output=True, text=True)
            if r2.returncode != 0:
                # non-fatal, but report
                raise Exception(r2.stderr.strip() or "failed to set autostart")

        # Create VM object
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
             iso: str | None = None, add_disks: List[int] | None = None, iso_dir: str = "", 
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
    
    # Check if VM is running
    statuses = parse_virsh_list()
    is_running = statuses.get(name) == "running"
    
    if cpu is not None and cpu != vm.cpu:
            # Set maximum vcpus first (config for next boot)
            result = subprocess.run(["virsh", "setvcpus", name, str(cpu), "--maximum", "--config"], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Warning: setvcpus maximum config failed: {result.stderr}")
            
            # Set current vcpus (config for next boot)
            result = subprocess.run(["virsh", "setvcpus", name, str(cpu), "--config"], capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Failed to set CPU config: {result.stderr.strip()}")
            
            # If running, also update live (maximum first, then current)
            if is_running:
                # First set live maximum
                result = subprocess.run(["virsh", "setvcpus", name, str(cpu), "--maximum", "--live"], capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"Warning: live CPU maximum update failed: {result.stderr}")
                # Then set live current
                result = subprocess.run(["virsh", "setvcpus", name, str(cpu), "--live"], capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"Warning: live CPU update failed: {result.stderr}")
            vm.cpu = cpu
    
    if memory is not None and memory != vm.memory:
        # Memory in MB, virsh expects KiB
        memory_kib = memory * 1024
        # Set maximum memory
        result = subprocess.run(["virsh", "setmaxmem", name, str(memory_kib), "--config"], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Warning: setmaxmem failed: {result.stderr}")
        # Set current memory  
        result = subprocess.run(["virsh", "setmem", name, str(memory_kib), "--config"], capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Failed to set memory: {result.stderr.strip()}")
        # If running, also update live
        if is_running:
            result = subprocess.run(["virsh", "setmem", name, str(memory_kib), "--live"], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Warning: live memory update failed: {result.stderr}")
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
        # Determine base directory for new VM disks
        # Use provided storage_path, or fall back to VM's existing storage_path, or use default
        if storage_path and os.path.isdir(storage_path):
            vms_root = os.path.join(storage_path, "vms")
            base_dir = os.path.join(vms_root, name)
            
            # Ensure parent directories are accessible for libvirt-qemu
            ensure_parent_permissions(vms_root)
            
            # Create vms root directory if it doesn't exist
            if not os.path.exists(vms_root):
                os.makedirs(vms_root, exist_ok=True)
                set_libvirt_permissions(vms_root)
            
            # Create VM directory
            os.makedirs(base_dir, exist_ok=True)
            set_libvirt_permissions(base_dir)
            # Update VM's storage_path
            vm.storage_path = storage_path
        elif vm.storage_path and os.path.isdir(vm.storage_path):
            vms_root = os.path.join(vm.storage_path, "vms")
            base_dir = os.path.join(vms_root, name)
            
            # Ensure parent directories are accessible for libvirt-qemu
            ensure_parent_permissions(vms_root)
            
            # Create vms root directory if it doesn't exist
            if not os.path.exists(vms_root):
                os.makedirs(vms_root, exist_ok=True)
                set_libvirt_permissions(vms_root)
            
            # Create VM directory
            os.makedirs(base_dir, exist_ok=True)
            set_libvirt_permissions(base_dir)
        else:
            base_dir = "/var/lib/libvirt/images"
        
        # Filter out 0 or invalid disk sizes
        valid_disks = [size for size in add_disks if size and size > 0]
        for size in valid_disks:
            disk_path = os.path.join(base_dir, f"{name}_{len(vm.disks) + 1}.qcow2")
            result = subprocess.run(["qemu-img", "create", "-f", "qcow2", disk_path, f"{size}G"], capture_output=True, text=True)
            if result.returncode == 0:
                # Set correct permissions for libvirt-qemu
                set_libvirt_permissions(disk_path)
                
                # Determine next available virtio device (vda is primary, use vdb, vdc, etc.)
                # Count existing disks to determine target device
                target_idx = len(vm.disks) + 1  # +1 because vda is disk 1
                target_device = f"vd{chr(ord('a') + target_idx)}"  # vdb, vdc, vdd, etc.
                
                # Attach disk to VM with explicit target device
                result = subprocess.run(["virsh", "attach-disk", name, disk_path, target_device, 
                                       "--driver", "qemu", "--subdriver", "qcow2", 
                                       "--targetbus", "virtio", "--persistent"], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    vm.disks.append(disk_path)
                else:
                    print(f"Warning: Could not attach disk {disk_path}: {result.stderr}")
                    # Clean up created disk file if attach failed
                    if os.path.exists(disk_path):
                        try:
                            os.remove(disk_path)
                        except Exception:
                            pass
    
    # Remove disks
    if remove_disks:
        for disk_path in remove_disks:
            if disk_path in vm.disks:
                # Detach disk from VM
                result = subprocess.run(["virsh", "detach-disk", name, disk_path, "--persistent"], capture_output=True, text=True)
                if result.returncode == 0:
                    # Remove from VM's disk list
                    vm.disks.remove(disk_path)
                    # Delete the disk file
                    if os.path.exists(disk_path) and disk_path.endswith('.qcow2'):
                        try:
                            os.remove(disk_path)
                        except Exception as e:
                            print(f"Warning: Could not delete disk file {disk_path}: {e}")
                else:
                    print(f"Warning: Could not detach disk {disk_path}: {result.stderr}")
    
    # Update network mode
    if network_mode is not None:
        # Map network_mode to network_bridge for storage
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
    return vm


def start_vm(name: str) -> None:
    """Start a virtual machine."""
    if shutil.which("virsh") is None:
        raise Exception("virsh not installed")
    result = subprocess.run(["virsh", "start", name], capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(result.stderr.strip() or "failed to start")


def shutdown_vm(name: str) -> None:
    """Shutdown a virtual machine (hard stop)."""
    if shutil.which("virsh") is None:
        raise Exception("virsh not installed")
    # Try graceful shutdown first
    subprocess.run(["virsh", "shutdown", name], capture_output=True, text=True)
    # If still running after 2 seconds, force destroy
    import time
    time.sleep(2)
    result = subprocess.run(["virsh", "destroy", name], capture_output=True, text=True)
    # destroy returns error if VM is already stopped, which is ok
    if result.returncode != 0 and "domain is not running" not in result.stderr.lower():
        raise Exception(result.stderr.strip() or "failed to stop")


def delete_vm(name: str) -> None:
    """Delete a virtual machine and remove it from storage."""
    if shutil.which("virsh") is None:
        raise Exception("virsh not installed")
    
    # Get VM info to delete only VM-specific disks
    vms = load_vms()
    vm = next((v for v in vms if v.name == name), None)
    
    # Stop VM if running
    subprocess.run(["virsh", "destroy", name], capture_output=True)
    
    # Undefine VM without removing storage (we'll do it selectively)
    result = subprocess.run(["virsh", "undefine", name, "--nvram"], capture_output=True, text=True)
    if result.returncode != 0:
        # Try without --nvram if it fails
        result = subprocess.run(["virsh", "undefine", name], capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(result.stderr.strip() or "failed to delete")
    
    # Delete only VM-specific disk files (qcow2 images, not ISOs)
    if vm and vm.disks:
        for disk in vm.disks:
            if os.path.exists(disk) and disk.endswith('.qcow2'):
                try:
                    os.remove(disk)
                except Exception as e:
                    print(f"Warning: Could not delete disk {disk}: {e}")
    
    # Delete cloud-init ISO if exists
    if vm and vm.cloud_init_iso and os.path.exists(vm.cloud_init_iso):
        try:
            os.remove(vm.cloud_init_iso)
        except Exception as e:
            print(f"Warning: Could not delete cloud-init ISO: {e}")
    
    # Remove from our storage
    vms = [v for v in load_vms() if v.name != name]
    save_vms(vms)


def list_vms_with_status() -> List[VirtualMachine]:
    """List all VMs with their current status from virsh."""
    existing = load_vms()
    statuses = parse_virsh_list()
    
    for vm in existing:
        vm.status = statuses.get(vm.name, vm.status)
        
        # Get resource usage stats for running VMs
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