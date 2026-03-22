"""
upservx backup – manage backups via the UpservX API.

Commands:
  upservx backup list
  upservx backup create [--target <name>]
  upservx backup status
"""

from cli.api import APIError, get_client
from cli.output import error, header, info, kv, ok, table, warn


def cmd_list(args) -> int:
    header("Backups")
    try:
        data = get_client().get("/backup/jobs")
    except APIError as e:
        error(str(e))
        return 1

    backups = data if isinstance(data, list) else data.get("backups", [])
    if not backups:
        warn("No backups found.")
        return 0

    rows = [
        {
            "name": b.get("name", "?"),
            "date": b.get("date") or b.get("created_at", "?"),
            "size": b.get("size", "?"),
            "status": b.get("status", "?"),
        }
        for b in backups
    ]
    table(rows, ["name", "date", "size", "status"])
    return 0


def cmd_create(args) -> int:
    payload = {}
    if args.target:
        payload["target"] = args.target
    info("Creating backup...")
    try:
        resp = get_client().post("/backup/jobs", payload or None)
        ok("Backup started.")
        if isinstance(resp, dict) and resp.get("message"):
            info(resp["message"])
    except APIError as e:
        error(str(e))
        return 1
    return 0


def cmd_status(args) -> int:
    header("Backup Status")
    try:
        data = get_client().get("/backup/cron-jobs")
    except APIError as e:
        error(str(e))
        return 1
    if isinstance(data, dict):
        kv(data, indent=2)
    else:
        print(data)
    return 0


def register(subparsers):
    p = subparsers.add_parser("backup", help="Manage backups")
    sp = p.add_subparsers(dest="backup_cmd", metavar="<action>")
    sp.required = True

    sp.add_parser("list", help="List all backups")

    create_p = sp.add_parser("create", help="Create a new backup")
    create_p.add_argument("--target", "-t", metavar="NAME", help="Backup target name")

    sp.add_parser("status", help="Show backup job status")

    p.set_defaults(func=_dispatch)


def _dispatch(args) -> int:
    dispatch = {
        "list": cmd_list,
        "create": cmd_create,
        "status": cmd_status,
    }
    handler = dispatch.get(args.backup_cmd)
    if handler:
        return handler(args)
    return 1
