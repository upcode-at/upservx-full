"""
upservx apps – manage App Store applications.

Commands:
  upservx apps list
  upservx apps install <app>
  upservx apps info <app>
"""

from cli.api import APIError, get_client
from cli.output import error, header, info, kv, ok, table, warn


def cmd_list(args) -> int:
    header("App Store")
    try:
        data = get_client().get("/api/app-store/apps")
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
        data = get_client().get(f"/api/app-store/apps/{args.app}")
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
    try:
        resp = get_client().post(f"/api/app-store/install", {"app_name": args.app})
        ok(f"App '{args.app}' installation started.")
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

    p.set_defaults(func=_dispatch)


def _dispatch(args) -> int:
    dispatch = {
        "list": cmd_list,
        "info": cmd_info,
        "install": cmd_install,
    }
    handler = dispatch.get(args.apps_cmd)
    if handler:
        return handler(args)
    return 1
