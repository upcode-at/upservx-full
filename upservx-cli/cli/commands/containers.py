"""
upservx containers – manage Docker containers via the UpservX API.

Commands:
  upservx containers list
  upservx containers start <name>
  upservx containers stop <name>
  upservx containers restart <name>
  upservx containers remove <name>
  upservx containers logs <name> [--lines N]
  upservx containers inspect <name>
"""

from cli.api import APIError, get_client
from cli.output import error, header, info, kv, ok, table, warn


def cmd_list(args) -> int:
    header("Containers")
    try:
        data = get_client().get("/containers")
    except APIError as e:
        error(str(e))
        return 1

    containers = data if isinstance(data, list) else data.get("containers", [])
    if not containers:
        warn("No containers found.")
        return 0

    rows = [
        {
            "name": c.get("name") or c.get("Names", ["?"])[0].lstrip("/"),
            "image": c.get("image") or c.get("Image", "?"),
            "status": c.get("status") or c.get("Status", "?"),
            "ports": _format_ports(c.get("ports") or c.get("Ports", [])),
        }
        for c in containers
    ]
    table(rows, ["name", "image", "status", "ports"])
    return 0


def _format_ports(ports) -> str:
    if not ports:
        return ""
    if isinstance(ports, str):
        return ports
    if isinstance(ports, list):
        parts = []
        for p in ports:
            if isinstance(p, dict):
                pub = p.get("PublicPort", "")
                priv = p.get("PrivatePort", "")
                parts.append(f"{pub}:{priv}" if pub else str(priv))
            else:
                parts.append(str(p))
        return ", ".join(parts)
    return str(ports)


def cmd_start(args) -> int:
    info(f"Starting container '{args.name}'...")
    try:
        get_client().post(f"/containers/{args.name}/start")
        ok(f"Container '{args.name}' started.")
    except APIError as e:
        error(str(e))
        return 1
    return 0


def cmd_stop(args) -> int:
    info(f"Stopping container '{args.name}'...")
    try:
        get_client().post(f"/containers/{args.name}/stop")
        ok(f"Container '{args.name}' stopped.")
    except APIError as e:
        error(str(e))
        return 1
    return 0


def cmd_restart(args) -> int:
    info(f"Restarting container '{args.name}'...")
    try:
        get_client().post(f"/containers/{args.name}/restart")
        ok(f"Container '{args.name}' restarted.")
    except APIError as e:
        error(str(e))
        return 1
    return 0


def cmd_remove(args) -> int:
    info(f"Removing container '{args.name}'...")
    try:
        get_client().delete(f"/containers/{args.name}")
        ok(f"Container '{args.name}' removed.")
    except APIError as e:
        error(str(e))
        return 1
    return 0


def cmd_logs(args) -> int:
    try:
        resp = get_client().get(f"/containers/{args.name}/logs?lines={args.lines}")
        logs = resp.get("logs") or resp.get("output") or str(resp)
        print(logs)
    except APIError as e:
        error(str(e))
        return 1
    return 0


def cmd_inspect(args) -> int:
    header(f"Container: {args.name}")
    try:
        data = get_client().get(f"/containers/{args.name}")
    except APIError as e:
        error(str(e))
        return 1
    if isinstance(data, dict):
        kv(data, indent=2)
    else:
        print(data)
    return 0


def register(subparsers):
    p = subparsers.add_parser("containers", help="Manage Docker containers", aliases=["c"])
    sp = p.add_subparsers(dest="containers_cmd", metavar="<action>")
    sp.required = True

    sp.add_parser("list", help="List all containers")

    for action in ("start", "stop", "restart", "remove", "inspect"):
        sub = sp.add_parser(action, help=f"{action.capitalize()} a container")
        sub.add_argument("name", help="Container name or ID")

    logs_p = sp.add_parser("logs", help="Show container logs")
    logs_p.add_argument("name", help="Container name or ID")
    logs_p.add_argument("--lines", "-n", type=int, default=100, metavar="N", help="Number of log lines (default: 100)")

    p.set_defaults(func=_dispatch)


def _dispatch(args) -> int:
    dispatch = {
        "list": cmd_list,
        "start": cmd_start,
        "stop": cmd_stop,
        "restart": cmd_restart,
        "remove": cmd_remove,
        "logs": cmd_logs,
        "inspect": cmd_inspect,
    }
    handler = dispatch.get(args.containers_cmd)
    if handler:
        return handler(args)
    return 1
