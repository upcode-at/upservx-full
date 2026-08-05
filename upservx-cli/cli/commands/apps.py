"""
upservx apps – manage App Store applications.

Commands:
  upservx apps list
  upservx apps install <app> [--name project] [--env KEY=VALUE]
  upservx apps info <app>
  upservx apps update <project>
"""

from cli.api import APIError, get_client
from cli.generated_api_types import AppInstallRequest
from cli.output import error, header, info, kv, ok, table, warn


def cmd_list(args) -> int:
    header("App Store")
    try:
        data = get_client().get("/containers/app-store/apps")
    except APIError as e:
        error(str(e))
        return 1

    apps = data if isinstance(data, list) else data.get("apps", [])
    if not apps:
        warn("No apps available.")
        return 0

    rows = [
        {
            "name": a.get("name", "?"),
            "category": a.get("category", "?"),
            "description": a.get("description", "")[:60],
        }
        for a in apps
    ]
    table(rows, ["name", "category", "description"])
    return 0


def cmd_info(args) -> int:
    header(f"App: {args.app}")
    try:
        data = get_client().get(f"/containers/app-store/apps/{args.app}")
    except APIError as e:
        error(str(e))
        return 1
    if isinstance(data, dict):
        kv(data, indent=2)
    else:
        print(data)
    return 0


def cmd_install(args) -> int:
    info(f"Installing '{args.app}'...")
    environment = {}
    for assignment in args.env:
        if "=" not in assignment:
            error(f"Invalid --env value '{assignment}'; expected KEY=VALUE")
            return 2
        name, value = assignment.split("=", 1)
        if not name:
            error("Environment variable names cannot be empty")
            return 2
        environment[name] = value
    try:
        payload: AppInstallRequest = {
            "custom_name": args.name,
            "environment": environment,
        }
        resp = get_client().post(
            f"/containers/app-store/apps/{args.app}/install", payload
        )
        ok(f"App '{args.app}' installed successfully.")
        if isinstance(resp, dict) and resp.get("message"):
            info(resp["message"])
    except APIError as e:
        error(str(e))
        return 1
    return 0


def cmd_update(args) -> int:
    info(f"Updating '{args.project}'...")
    try:
        resp = get_client().post(
            f"/containers/app-store/apps/{args.project}/update", {}
        )
        ok(f"App Store project '{args.project}' updated successfully.")
        if isinstance(resp, dict) and resp.get("message"):
            info(resp["message"])
    except APIError as e:
        error(str(e))
        return 1
    return 0


def register(subparsers):
    p = subparsers.add_parser("apps", help="Browse and install apps from the App Store")
    sp = p.add_subparsers(dest="apps_cmd", metavar="<action>")
    sp.required = True

    sp.add_parser("list", help="List available apps")

    info_p = sp.add_parser("info", help="Show app details")
    info_p.add_argument("app", help="App name")

    install_p = sp.add_parser("install", help="Install an app")
    install_p.add_argument("app", help="App name")
    install_p.add_argument("--name", help="Custom Compose project name")
    install_p.add_argument(
        "--env",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Set an application variable (repeatable; secrets are not printed)",
    )

    update_p = sp.add_parser("update", help="Update an installed App Store project")
    update_p.add_argument("project", help="Installed Compose project name")

    p.set_defaults(func=_dispatch)


def _dispatch(args) -> int:
    dispatch = {
        "list": cmd_list,
        "info": cmd_info,
        "install": cmd_install,
        "update": cmd_update,
    }
    handler = dispatch.get(args.apps_cmd)
    if handler:
        return handler(args)
    return 1
