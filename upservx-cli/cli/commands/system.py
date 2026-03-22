"""
upservx system – system information and monitoring.

Commands:
  upservx system info
  upservx system stats
"""

from cli.api import APIError, get_client
from cli.output import error, header, info, kv, table, warn


def cmd_info(args) -> int:
    header("System Information")
    try:
        data = get_client().get("/metrics")
    except APIError as e:
        error(str(e))
        return 1

    cpu     = data.get("cpu") or {}
    mem     = data.get("memory") or {}
    storage = data.get("storage") or {}
    info_data = {
        "CPU":          cpu.get("model", "?"),
        "Cores":        str(cpu.get("cores", "?")),
        "Architecture": data.get("architecture", "?"),
        "Kernel":       data.get("kernel", "?"),
        "Memory":       f"{mem.get('total', '?')} GB",
        "Disk":         f"{storage.get('total', '?')} GB",
        "GPU":          data.get("gpu", "?"),
        "Uptime":       data.get("uptime", "?"),
    }
    kv(info_data, indent=2)
    print()

    # Services sub-table
    services = data.get("services", [])
    if services:
        header("Service Status")
        table(
            [{"name": s["name"], "status": s["status"]} for s in services],
            ["name", "status"],
        )
    return 0


def cmd_stats(args) -> int:
    header("System Stats")
    try:
        data = get_client().get("/metrics")
    except APIError as e:
        error(str(e))
        return 1

    cpu     = data.get("cpu") or {}
    mem     = data.get("memory") or {}
    storage = data.get("storage") or {}
    net     = data.get("network") or {}
    stats = {
        "CPU":     f"{cpu.get('usage', '?')}%  ({cpu.get('cores', '?')} cores, {cpu.get('model', '')})",
        "Memory":  f"{mem.get('used', '?')} GB / {mem.get('total', '?')} GB  ({mem.get('usage', '?')}%)",
        "Disk":    f"{storage.get('used', '?')} GB / {storage.get('total', '?')} GB  ({storage.get('usage', '?')}%)",
        "Network": f"↓ {net.get('in', '?')} MB/s  ↑ {net.get('out', '?')} MB/s",
        "Uptime":  data.get("uptime", "?"),
        "Kernel":  data.get("kernel", "?"),
    }
    kv(stats, indent=2)
    print()
    return 0


def cmd_services(args) -> int:
    header("SystemD Services")
    try:
        data = get_client().get("/services")
    except APIError as e:
        error(str(e))
        return 1

    services = data if isinstance(data, list) else data.get("services", [])
    if not services:
        warn("No services found.")
        return 0

    rows = [
        {
            "name": s.get("name", "?"),
            "status": s.get("status") or s.get("ActiveState", "?"),
            "enabled": s.get("enabled") or s.get("UnitFileState", "?"),
        }
        for s in services
    ]
    table(rows, ["name", "status", "enabled"])
    return 0


def register(subparsers):
    p = subparsers.add_parser("system", help="System information and stats", aliases=["sys"])
    sp = p.add_subparsers(dest="system_cmd", metavar="<action>")
    sp.required = True

    sp.add_parser("info", help="Show system information")
    sp.add_parser("stats", help="Show CPU, memory and disk usage")
    sp.add_parser("services", help="List systemd services")

    p.set_defaults(func=_dispatch)


def _dispatch(args) -> int:
    dispatch = {
        "info": cmd_info,
        "stats": cmd_stats,
        "services": cmd_services,
    }
    handler = dispatch.get(args.system_cmd)
    if handler:
        return handler(args)
    return 1
