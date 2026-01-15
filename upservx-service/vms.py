"""
Virtual machine management utilities using libvirt/KVM.
"""

import os
import json
import subprocess
import shutil
import tempfile
from typing import List
from datetime import datetime
from models import VirtualMachine


VM_FILE = os.path.join(os.path.dirname(__file__), "vms.json")


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
              network_bridge: str = "virbr0", autostart: bool = False, cloud_init: str | None = None) -> VirtualMachine:
    """Create a new virtual machine using virt-install.

    Supports optional cloud-init user-data (string). If `cloud_init` is provided
    a small seed ISO will be created and attached as a CD-ROM.
    """
    if shutil.which("virt-install") is None:
        raise Exception("virt-install not installed")

    iso_path = os.path.join(iso_dir, iso) if iso else None
    if iso_path and not os.path.isfile(iso_path):
        raise Exception("iso not found")

    if shutil.which("qemu-img") is None:
        raise Exception("qemu-img not installed")

    disk_args = []
    disk_paths = []
    for idx, size in enumerate(disks or [20], start=1):
        disk_path = f"/var/lib/libvirt/images/{name}_{idx}.qcow2"
        disk_paths.append(disk_path)
        r = subprocess.run(["qemu-img", "create", "-f", "qcow2", disk_path, f"{size}G"], capture_output=True, text=True)
        if r.returncode != 0:
            raise Exception(r.stderr.strip() or "failed to create disk")
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

            seed_iso_path = f"/var/lib/libvirt/images/{name}_seed.iso"
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

            # attach as CD-ROM
            disk_args.extend(["--disk", f"path={seed_iso_path},device=cdrom"])

        cmd = [
            "virt-install",
            "--name", name,
            "--ram", str(memory),
            "--vcpus", str(cpu),
            *disk_args,
            "--os-variant", "generic",
            "--network", f"bridge={network_bridge}",
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
             iso: str | None = None, add_disks: List[int] | None = None, iso_dir: str = "", autostart: bool | None = None) -> VirtualMachine:
    """Update an existing virtual machine configuration."""
    if shutil.which("virsh") is None:
        raise Exception("virsh not installed")
    
    vms = load_vms()
    vm = next((v for v in vms if v.name == name), None)
    if not vm:
        raise Exception("vm not found")
    
    print(f"Updating VM {name}: cpu={cpu}, memory={memory}, autostart={autostart}, add_disks={add_disks}")
    
    # Check if VM is running
    statuses = parse_virsh_list()
    is_running = statuses.get(name) == "running"
    print(f"VM {name} is_running: {is_running}")
    
    if cpu is not None and cpu != vm.cpu:
        print(f"Updating CPU from {vm.cpu} to {cpu}")
        # Set maximum vcpus first
        result = subprocess.run(["virsh", "setvcpus", name, str(cpu), "--maximum", "--config"], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Warning: setvcpus maximum failed: {result.stderr}")
        # Set current vcpus
        result = subprocess.run(["virsh", "setvcpus", name, str(cpu), "--config"], capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Failed to set CPU: {result.stderr.strip()}")
        # If running, also update live
        if is_running:
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
        # Filter out 0 or invalid disk sizes
        valid_disks = [size for size in add_disks if size and size > 0]
        for size in valid_disks:
            disk_path = f"/var/lib/libvirt/images/{name}_{len(vm.disks) + 1}.qcow2"
            result = subprocess.run(["qemu-img", "create", "-f", "qcow2", disk_path, f"{size}G"], capture_output=True, text=True)
            if result.returncode == 0:
                # Attach disk to VM
                subprocess.run(["virsh", "attach-disk", name, disk_path, "--driver", "qemu", "--subdriver", "qcow2", "--targetbus", "virtio", "--persistent"], capture_output=True)
                vm.disks.append(disk_path)
    
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
    
    for idx, vm in enumerate(existing, start=1):
        vm.id = idx
    
    return existing