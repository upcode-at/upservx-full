"""
Virtual machine management utilities using libvirt/KVM.
"""

import os
import json
import subprocess
import shutil
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
            statuses[parts[1]] = parts[2]
    return statuses


def create_vm(name: str, cpu: int, memory: int, iso: str, disks: List[int], iso_dir: str) -> VirtualMachine:
    """Create a new virtual machine using virt-install."""
    if shutil.which("virt-install") is None:
        raise Exception("virt-install not installed")
    
    iso_path = os.path.join(iso_dir, iso)
    if not os.path.isfile(iso_path):
        raise Exception("iso not found")

    disk_args = []
    disk_paths = []
    for idx, size in enumerate(disks or [20], start=1):
        disk_path = f"/var/lib/libvirt/images/{name}_{idx}.qcow2"
        disk_paths.append(disk_path)
        subprocess.run(["qemu-img", "create", "-f", "qcow2", disk_path, f"{size}G"], capture_output=True)
        disk_args.extend(["--disk", f"path={disk_path},size={size}"])

    cmd = [
        "virt-install",
        "--name", name,
        "--ram", str(memory),
        "--vcpus", str(cpu),
        *disk_args,
        "--cdrom", iso_path,
        "--os-variant", "generic",
        "--network", "bridge=virbr0",
        "--graphics", "vnc",
        "--hvm",
        "--noautoconsole",
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(result.stderr.strip() or "failed to create")

    # Create VM object
    vms = load_vms()
    vm = VirtualMachine(
        id=len(vms) + 1,
        name=name,
        status="running",
        cpu=cpu,
        memory=memory,
        iso=iso,
        disks=disk_paths,
        created=datetime.utcnow().date().isoformat(),
    )
    vms.append(vm)
    save_vms(vms)
    return vm


def update_vm(name: str, cpu: int | None = None, memory: int | None = None, 
             iso: str | None = None, add_disks: List[int] | None = None, iso_dir: str = "") -> VirtualMachine:
    """Update an existing virtual machine configuration."""
    if shutil.which("virsh") is None:
        raise Exception("virsh not installed")
    
    vms = load_vms()
    vm = next((v for v in vms if v.name == name), None)
    if not vm:
        raise Exception("vm not found")
    
    if cpu is not None:
        subprocess.run(["virsh", "setvcpus", name, str(cpu), "--config"], capture_output=True)
        vm.cpu = cpu
    
    if memory is not None:
        subprocess.run(["virsh", "setmem", name, str(memory * 1024), "--config"], capture_output=True)
        vm.memory = memory
    
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
        for size in add_disks:
            disk_path = f"/var/lib/libvirt/images/{name}_{len(vm.disks) + 1}.qcow2"
            subprocess.run(["qemu-img", "create", "-f", "qcow2", disk_path, f"{size}G"], capture_output=True)
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
    """Shutdown a virtual machine."""
    if shutil.which("virsh") is None:
        raise Exception("virsh not installed")
    result = subprocess.run(["virsh", "shutdown", name], capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(result.stderr.strip() or "failed to shutdown")


def delete_vm(name: str) -> None:
    """Delete a virtual machine and remove it from storage."""
    if shutil.which("virsh") is None:
        raise Exception("virsh not installed")
    
    subprocess.run(["virsh", "destroy", name], capture_output=True)
    result = subprocess.run(["virsh", "undefine", name, "--remove-all-storage"], capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(result.stderr.strip() or "failed to delete")
    
    # Remove from our storage
    vms = [vm for vm in load_vms() if vm.name != name]
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