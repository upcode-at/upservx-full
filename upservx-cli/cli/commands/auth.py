"""
upservx auth – login, logout, whoami.

Commands:
  upservx auth login   [--username U] [--password P]
  upservx auth logout
  upservx auth whoami
"""

import getpass
import sys

from cli.api import APIError, get_client
from cli.config import (
    encode_credentials,
    get_username_from_config,
    load_config,
    save_config,
)
from cli.output import error, header, info, kv, ok, warn


def cmd_login(args) -> int:
    header("UpservX Login")

    cfg = load_config()

    username = args.username or input("Username: ").strip()
    if not username:
        error("Username cannot be empty.")
        return 1

    password = args.password or getpass.getpass("Password: ")
    if not password:
        error("Password cannot be empty.")
        return 1

    # Temporarily build credentials and test against the API
    from cli.api import APIClient
    import requests

    credentials = encode_credentials(username, password)
    session = requests.Session()
    session.headers.update({
        "Accept": "application/json",
        "Authorization": f"Basic {credentials}",
    })

    api_url = cfg["api_url"].rstrip("/")
    try:
        resp = session.get(f"{api_url}/", timeout=10)
    except Exception as e:
        error(f"Cannot reach API at {api_url}: {e}")
        return 1

    if resp.status_code == 401:
        error("Invalid credentials.")
        return 1
    if resp.status_code == 403:
        error("Access denied.")
        return 1
    if not resp.ok:
        error(f"Login check failed: HTTP {resp.status_code}")
        return 1

    # Credentials are valid – persist them
    cfg["credentials"] = credentials
    cfg.pop("token", None)  # clear any old bearer token
    save_config(cfg)

    ok(f"Logged in as [bold]{username}[/bold]")
    return 0


def cmd_logout(args) -> int:
    cfg = load_config()
    changed = False

    if cfg.get("credentials"):
        cfg["credentials"] = ""
        changed = True
    if cfg.get("token"):
        cfg["token"] = ""
        changed = True

    if changed:
        save_config(cfg)
        ok("Logged out. Credentials removed.")
    else:
        warn("Not logged in.")
    return 0


def cmd_whoami(args) -> int:
    username = get_username_from_config()
    cfg = load_config()

    if not username and not cfg.get("token"):
        warn("Not logged in. Run: upservx auth login")
        return 1

    header("Current Session")
    data = {
        "user":    username if username else "(api-key)",
        "api_url": cfg.get("api_url", ""),
        "auth":    "Basic" if cfg.get("credentials") else "Bearer" if cfg.get("token") else "none",
    }
    kv(data, indent=2)

    # Verify session is still valid
    try:
        get_client().get("/")
        ok("Session is active.")
    except APIError as e:
        if e.status == 401:
            warn("Session expired or invalid. Run: upservx auth login")
        else:
            warn(str(e))
    return 0


def register(subparsers):
    p = subparsers.add_parser("auth", help="Login, logout and session management")
    sp = p.add_subparsers(dest="auth_cmd", metavar="<action>")
    sp.required = True

    login_p = sp.add_parser("login", help="Authenticate with username and password")
    login_p.add_argument("--username", "-u", metavar="USER", help="Username")
    login_p.add_argument("--password", "-p", metavar="PASS", help="Password (unsafe – prefer interactive prompt)")

    sp.add_parser("logout", help="Remove stored credentials")
    sp.add_parser("whoami", help="Show current session info")

    p.set_defaults(func=_dispatch)


def _dispatch(args) -> int:
    dispatch = {
        "login": cmd_login,
        "logout": cmd_logout,
        "whoami": cmd_whoami,
    }
    handler = dispatch.get(args.auth_cmd)
    if handler:
        return handler(args)
    return 1
