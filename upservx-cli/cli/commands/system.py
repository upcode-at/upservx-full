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
        data = get_client().get("/api/system/info")
    except APIError as e:
        error(str(e))
        return 1
    if isinstance(data, dict):
        kv(data, indent=2)
    else:
        print(data)
    return 0


def cmd_stats(args) -> int:
    header("System Stats")
    try:
        data = get_client().get("/api/system/stats")
    except APIError as e:
        error(str(e))
        return 1

    stats = {
        "CPU":    f"{data.get('cpu_percent', '?')}%",
        "Memory": f"{data.get('memory_used', '?')} / {data.get('memory_total', '?')} ({data.get('memory_percent', '?')}%)",
        "Disk":   f"{data.get('disk_used', '?')} / {data.get('disk_total', '?')} ({data.get('disk_percent', '?')}%)",
        "Uptime": data.get("uptime", "?"),
    }
    kv(stats, indent=2)
    print()
    return 0


def cmd_services(args) -> int:
    header("SystemD Services")
    try:
        data = get_client().get("/api/services")
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
