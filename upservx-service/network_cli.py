#!/usr/bin/env python3
"""Command line utility for network configuration."""

import argparse
import subprocess
import sys

from main import get_network_interfaces, load_network_settings, save_network_settings


def list_interfaces(_args: argparse.Namespace) -> None:
    """Print available network interfaces with current IP information."""
    interfaces = get_network_interfaces()
    for iface in interfaces:
        print(f"{iface.name}\t{iface.ip}\t{iface.netmask}\tgw {iface.gateway}")


def set_ip(args: argparse.Namespace) -> None:
    """Configure a static IP for the given interface."""
    cmd_flush = ["ip", "addr", "flush", "dev", args.interface]
    subprocess.run(cmd_flush, check=True)
    addr = f"{args.ip}/{args.netmask}"
    cmd_add = ["ip", "addr", "add", addr, "dev", args.interface]
    subprocess.run(cmd_add, check=True)
    if args.gateway:
        cmd_gw = ["ip", "route", "replace", "default", "via", args.gateway, "dev", args.interface]
        subprocess.run(cmd_gw, check=True)


def set_dns(args: argparse.Namespace) -> None:
    """Update DNS settings saved by the service."""
    settings = load_network_settings()
    settings.dns_primary = args.primary
    settings.dns_secondary = args.secondary
    save_network_settings(settings)
    try:
        with open("/etc/resolv.conf", "w") as f:
            f.write(f"nameserver {settings.dns_primary}\n")
            f.write(f"nameserver {settings.dns_secondary}\n")
    except PermissionError:
        print("Permission denied writing /etc/resolv.conf", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage network settings")
    subparsers = parser.add_subparsers(dest="command")

    p_list = subparsers.add_parser("list", help="List interfaces")
    p_list.set_defaults(func=list_interfaces)

    p_set_ip = subparsers.add_parser("set-ip", help="Set static IP for interface")
    p_set_ip.add_argument("interface", help="Network interface name")
    p_set_ip.add_argument("ip", help="IPv4 address")
    p_set_ip.add_argument("netmask", help="Netmask bits, e.g. 24")
    p_set_ip.add_argument("--gateway", help="Default gateway", default=None)
    p_set_ip.set_defaults(func=set_ip)

    p_dns = subparsers.add_parser("set-dns", help="Configure DNS servers")
    p_dns.add_argument("primary", help="Primary DNS server")
    p_dns.add_argument("secondary", help="Secondary DNS server")
    p_dns.set_defaults(func=set_dns)

    args = parser.parse_args()
    if hasattr(args, "func"):
        try:
            args.func(args)
        except subprocess.CalledProcessError as exc:
            print(f"Command failed: {exc}", file=sys.stderr)
            sys.exit(exc.returncode)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
