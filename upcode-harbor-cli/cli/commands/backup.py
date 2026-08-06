"""
upcode-harbor backup – manage backups via the Upcode Harbor API.

Commands:
  upcode-harbor backup list
  upcode-harbor backup create --name NAME --type TYPE --target TARGET --server-id ID
  upcode-harbor backup status
"""

from cli.api import APIError, get_client
from cli.generated_api_types import BackupJobCreate
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
            "date": b.get("last_run") or b.get("created", "?"),
            "size": b.get("last_size", "?"),
            "status": b.get("status", "?"),
        }
        for b in backups
    ]
    table(rows, ["name", "date", "size", "status"])
    return 0


def cmd_create(args) -> int:
    payload: BackupJobCreate = {
        "name": args.name,
        "backup_type": args.backup_type,
        "targets": args.targets,
        "schedule": args.schedule,
        "server_id": args.server_id,
        "retention_days": args.retention_days,
        "compression": not args.no_compression,
    }
    info("Creating backup job...")
    try:
        resp = get_client().post("/backup/jobs", payload)
        job_id = resp.get("id") if isinstance(resp, dict) else None
        ok("Backup job created.")
        if isinstance(resp, dict) and resp.get("message"):
            info(resp["message"])
        if args.run_now and job_id is not None:
            get_client().post(f"/backup/jobs/{job_id}/execute")
            ok("Backup queued.")
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
    create_p.add_argument("--name", required=True, help="Backup job name")
    create_p.add_argument(
        "--type", dest="backup_type", required=True,
        choices=("vm", "container", "system", "database"),
        help="Backup type",
    )
    create_p.add_argument(
        "--target", "-t", dest="targets", action="append", required=True,
        metavar="TARGET", help="Target path, vm:NAME, or container:NAME; repeatable",
    )
    create_p.add_argument("--server-id", type=int, required=True, help="Destination server ID")
    create_p.add_argument("--schedule", default="0 2 * * *", help="Five-field cron schedule")
    create_p.add_argument("--retention-days", type=int, default=30)
    create_p.add_argument("--no-compression", action="store_true")
    create_p.add_argument("--run-now", action="store_true", help="Queue the job after creating it")

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
