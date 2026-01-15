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
            cmd.extend(["--cdrom", iso_path])

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