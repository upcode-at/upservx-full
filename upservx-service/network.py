"""
Network interface and settings management utilities.
"""

import os
import json
import subprocess
import socket
import psutil
import ipaddress
from typing import List
from models import NetworkInterfaceInfo, NetworkSettingsModel, InterfaceConfigModel


NETWORK_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "network_settings.json")


def _format_bytes(num: int) -> str:
    """Format bytes into human-readable format."""
    step = 1024.0
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < step:
            return f"{num:.1f} {unit}"
        num /= step
    return f"{num:.1f} PB"


def _infer_iface_type(name: str) -> str:
    """Infer network interface type from name."""
    if name.startswith(("wl", "wifi")):
        return "WiFi"
    if name.startswith("br"):
        return "Bridge"
    if name.startswith(("docker", "veth")):
        return "Virtual"
    return "Ethernet"


def _default_gateways() -> dict[str, str]:
    """Get default gateways for network interfaces."""
    gateways: dict[str, str] = {}
    try:
        output = subprocess.check_output(["ip", "route", "show", "default"], text=True)
        for line in output.splitlines():
            parts = line.split()
            if not parts or parts[0] != "default":
                continue
            gw = parts[2] if len(parts) >= 3 else "-"
            if "dev" in parts:
                idx = parts.index("dev")
                if idx + 1 < len(parts):
                    iface = parts[idx + 1]
                    gateways[iface] = gw
    except Exception:
        pass
    return gateways


def get_network_interfaces() -> List[NetworkInterfaceInfo]:
    """Get detailed information about all network interfaces."""
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    io_counters = psutil.net_io_counters(pernic=True)
    gateways = _default_gateways()

    interfaces: List[NetworkInterfaceInfo] = []
    for name, addr_list in addrs.items():
        stat = stats.get(name)
        if not stat:
            continue
        
        ip = "-"
        netmask = "-"
        mac = "-"
        
        for addr in addr_list:
            if addr.family == socket.AF_INET:
                ip = addr.address
                netmask = addr.netmask or "-"
            elif addr.family == psutil.AF_LINK or getattr(socket, "AF_PACKET", 17) == addr.family:
                mac = addr.address
        
        io = io_counters.get(name)
        rx = _format_bytes(io.bytes_recv) if io else "0 B"
        tx = _format_bytes(io.bytes_sent) if io else "0 B"
        speed = f"{stat.speed} Mbps" if stat.speed > 0 else "-"
        
        interfaces.append(
            NetworkInterfaceInfo(
                name=name,
                type=_infer_iface_type(name),
                status="up" if stat.isup else "down",
                ip=ip,
                netmask=netmask,
                gateway=gateways.get(name, "-"),
                mac=mac,
                speed=speed,
                rx=rx,
                tx=tx,
            )
        )
    return interfaces


def _system_nameservers() -> tuple[str, str]:
    """Get primary and secondary nameservers from /etc/resolv.conf."""
    primary = "8.8.8.8"
    secondary = "8.8.4.4"
    try:
        with open("/etc/resolv.conf") as f:
            nameservers = [
                line.split()[1]
                for line in f
                if line.strip().startswith("nameserver") and len(line.split()) >= 2
            ]
        if nameservers:
            primary = nameservers[0]
            if len(nameservers) > 1:
                secondary = nameservers[1]
    except Exception:
        pass
    return primary, secondary


def load_network_settings() -> NetworkSettingsModel:
    """Load network settings from file or system defaults."""
    if os.path.exists(NETWORK_SETTINGS_FILE):
        try:
            with open(NETWORK_SETTINGS_FILE) as f:
                data = json.load(f)
                primary, secondary = _system_nameservers()
                return NetworkSettingsModel(
                    dns_primary=data.get("dns_primary", primary),
                    dns_secondary=data.get("dns_secondary", secondary),
                )
        except Exception:
            pass
    
    primary, secondary = _system_nameservers()
    return NetworkSettingsModel(dns_primary=primary, dns_secondary=secondary)


def save_network_settings(settings: NetworkSettingsModel) -> None:
    """Save network settings to file."""
    with open(NETWORK_SETTINGS_FILE, "w") as f:
        json.dump(settings.dict(), f)


def _netmask_to_prefix(netmask: str) -> int:
    """Convert a netmask like '255.255.255.0' to a CIDR prefix length (e.g. 24)."""
    try:
        network = ipaddress.IPv4Network(f"0.0.0.0/{netmask}")
        return network.prefixlen
    except Exception:
        # Fallback: count bits
        try:
            parts = [int(p) for p in netmask.split('.')]
            bits = ''.join(format(p, '08b') for p in parts)
            return bits.count('1')
        except Exception:
            return 24


def configure_interface(name: str, cfg: InterfaceConfigModel) -> None:
    """Apply configuration to a network interface.

    This attempts to bring the interface up/down, configure DHCP or static
    IP and set the default gateway. Commands use `ip` and `dhclient` and
    therefore require appropriate system privileges.
    """
    try:
        # Bring interface up/down as requested
        if not cfg.enabled:
            subprocess.check_call(["ip", "link", "set", "dev", name, "down"])
            return

        subprocess.check_call(["ip", "link", "set", "dev", name, "up"])

        if cfg.method == "dhcp":
            # Flush existing addresses first to remove any old static/secondary
            # addresses that might otherwise remain when switching to DHCP.
            subprocess.check_call(["ip", "addr", "flush", "dev", name])

            # Try to release any existing DHCP lease and request a new one
            try:
                subprocess.call(["dhclient", "-r", name])
            except Exception:
                pass
            subprocess.check_call(["dhclient", name])
        else:
            # Static configuration
            # Flush existing addresses on the interface
            subprocess.check_call(["ip", "addr", "flush", "dev", name])

            if cfg.ip and cfg.netmask:
                prefix = _netmask_to_prefix(cfg.netmask)
                subprocess.check_call(["ip", "addr", "add", f"{cfg.ip}/{prefix}", "dev", name])

            if cfg.gateway:
                # Replace the default route to use this gateway for the interface
                subprocess.check_call(["ip", "route", "replace", "default", "via", cfg.gateway, "dev", name])

    except subprocess.CalledProcessError as e:
        raise Exception(f"Failed to configure interface: {e}")