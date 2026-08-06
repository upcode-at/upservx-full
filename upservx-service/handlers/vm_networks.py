"""Libvirt virtual network management for internal VM networks."""

import os
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from typing import List, Optional

from lib.logger import log_vm


def _virsh(*args) -> subprocess.CompletedProcess:
    if shutil.which("virsh") is None:
        raise RuntimeError("libvirt is not installed")
    return subprocess.run(["virsh", *args], capture_output=True, text=True)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

def list_vm_networks() -> List[dict]:
    """Return all libvirt networks (active and inactive)."""
    if shutil.which("virsh") is None:
        return []

    result = _virsh("net-list", "--all")
    if result.returncode != 0:
        reason = result.stderr.strip() or "virsh net-list failed"
        log_vm(f"VM network listing unavailable: {reason}", error=True)
        return []

    networks = []
    lines = result.stdout.strip().splitlines()
    # Skip header lines (first two: header + separator)
    for line in lines[2:]:
        parts = line.split()
        if len(parts) < 3:
            continue
        name = parts[0]
        active = parts[1].lower() == "yes"
        autostart = parts[2].lower() == "yes"
        networks.append({
            "name": name,
            "active": active,
            "autostart": autostart,
            "details": _get_network_details(name),
        })
    return networks


def _get_network_details(name: str) -> dict:
    """Parse virsh net-dumpxml to get subnet, dhcp, forward mode."""
    result = _virsh("net-dumpxml", name)
    if result.returncode != 0:
        return {}
    try:
        root = ET.fromstring(result.stdout)
        forward_el = root.find("forward")
        forward_mode = forward_el.get("mode", "") if forward_el is not None else "isolated"
        ip_el = root.find("ip")
        subnet = ""
        dhcp_range = ""
        if ip_el is not None:
            address = ip_el.get("address", "")
            netmask = ip_el.get("netmask", "")
            if address and netmask:
                subnet = f"{address}/{_netmask_to_prefix(netmask)}"
            dhcp_el = ip_el.find("dhcp")
            if dhcp_el is not None:
                range_el = dhcp_el.find("range")
                if range_el is not None:
                    dhcp_range = f"{range_el.get('start', '')} – {range_el.get('end', '')}"
        bridge_el = root.find("bridge")
        bridge_name = bridge_el.get("name", "") if bridge_el is not None else ""
        return {
            "forward_mode": forward_mode,
            "subnet": subnet,
            "dhcp_range": dhcp_range,
            "bridge": bridge_name,
        }
    except Exception:
        return {}


def _netmask_to_prefix(netmask: str) -> int:
    """Convert dotted-decimal netmask to prefix length."""
    try:
        return sum(bin(int(x)).count("1") for x in netmask.split("."))
    except Exception:
        return 24


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def create_vm_network(name: str) -> dict:
    """Create and start a new isolated libvirt network (no IP, no DHCP).

    VMs attached to this network can communicate on L2 only;
    all IP configuration is done inside the VMs themselves.

    Args:
        name: Network name (alphanumeric, hyphens/underscores allowed).
    """
    if not name or not name.replace("-", "").replace("_", "").isalnum():
        raise Exception("Invalid network name – use alphanumeric characters and hyphens only")

    # Check for name collision
    existing = _virsh("net-info", name)
    if existing.returncode == 0:
        raise Exception(f"Network '{name}' already exists")

    # Pure L2 isolated network – no <ip> element, no DHCP, no forwarding
    xml = (
        f"<network>\n"
        f"  <name>{name}</name>\n"
        f"  <bridge name='virbr-{name[:10]}' stp='on' delay='0'/>\n"
        f"</network>\n"
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
        f.write(xml)
        tmp_path = f.name

    try:
        r = _virsh("net-define", tmp_path)
        if r.returncode != 0:
            raise Exception(r.stderr.strip() or "net-define failed")

        r = _virsh("net-start", name)
        if r.returncode != 0:
            _virsh("net-undefine", name)
            raise Exception(r.stderr.strip() or "net-start failed")

        log_vm(f"Created internal network [{name}]")
        return {
            "name": name,
            "active": True,
            "autostart": False,
            "details": _get_network_details(name),
        }
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def delete_vm_network(name: str) -> None:
    """Stop and remove a libvirt network."""
    # Cannot delete built-in 'default' network if VMs depend on it
    if name == "default":
        raise Exception("The 'default' network cannot be deleted")

    # Destroy (stop) if active
    if _is_network_active(name):
        r = _virsh("net-destroy", name)
        if r.returncode != 0:
            raise Exception(r.stderr.strip() or "net-destroy failed")

    r = _virsh("net-undefine", name)
    if r.returncode != 0:
        raise Exception(r.stderr.strip() or "net-undefine failed")

    log_vm(f"Deleted internal network [{name}]")


# ---------------------------------------------------------------------------
# Start / Stop
# ---------------------------------------------------------------------------

def _is_network_active(name: str) -> bool:
    info = _virsh("net-info", name)
    if info.returncode != 0:
        raise Exception(f"Network '{name}' not found")
    return any(
        "Active:" in line and "yes" in line.lower()
        for line in info.stdout.splitlines()
    )


def start_vm_network(name: str) -> None:
    if _is_network_active(name):
        return  # already running — no-op
    r = _virsh("net-start", name)
    if r.returncode != 0:
        raise Exception(r.stderr.strip() or "net-start failed")
    log_vm(f"Started network [{name}]")


def stop_vm_network(name: str) -> None:
    if not _is_network_active(name):
        return  # already stopped — no-op
    r = _virsh("net-destroy", name)
    if r.returncode != 0:
        raise Exception(r.stderr.strip() or "net-destroy failed")
    log_vm(f"Stopped network [{name}]")
