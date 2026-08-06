"""
upcode-harbor auth – login, logout, whoami.

Commands:
  upcode-harbor auth login   [--username U] [--password P]
  upcode-harbor auth logout
  upcode-harbor auth whoami
"""

import getpass
import sys

from cli.api import APIError, get_client
from cli.config import (
    get_username_from_config,
    load_config,
    save_config,
)
from cli.output import error, header, info, kv, ok, warn


def cmd_login(args) -> int:
    header("Upcode Harbor Login")

    cfg = load_config()

    username = args.username or input("Username: ").strip()
    if not username:
        error("Username cannot be empty.")
        return 1

    password = args.password or getpass.getpass("Password: ")
    if not password:
        error("Password cannot be empty.")
        return 1

    import requests

    session = requests.Session()
    session.headers.update({"Accept": "application/json"})

    api_url = cfg["api_url"].rstrip("/")
    try:
        resp = session.post(
            f"{api_url}/auth/login",
            json={"username": username, "password": password},
            timeout=10,
        )
    except Exception as e:
        error(f"Cannot reach API at {api_url}: {e}")
        return 1

    if resp.status_code == 401:
        error("Invalid credentials.")
        return 1
    if resp.status_code == 403:
        error("Access denied.")
        return 1
    if resp.status_code == 429:
        error("Too many login attempts. Please retry in a minute.")
        return 1
    if not resp.ok:
        error(f"Login check failed: HTTP {resp.status_code}")
        return 1

    try:
        data = resp.json()
    except Exception:
        data = {}

    if data.get("2fa_required"):
        login_token = data.get("login_token", "")
        if not login_token:
            error("2FA is required but the API did not return a login token.")
            return 1
        code = args.totp or getpass.getpass("2FA code: ").strip()
        if not code:
            error("2FA code cannot be empty.")
            return 1
        try:
            resp = session.post(
                f"{api_url}/auth/2fa/complete",
                json={"login_token": login_token, "code": code},
                timeout=10,
            )
        except Exception as e:
            error(f"Cannot complete 2FA login: {e}")
            return 1
        if not resp.ok:
            error("Invalid or expired 2FA code.")
            return 1
        try:
            data = resp.json()
        except Exception:
            data = {}

    # Browser logins use an HttpOnly cookie; the CLI extracts that cookie from
    # its own requests session and persists the token as a Bearer credential.
    session_token = data.get("session_token", "") or session.cookies.get("auth", "")
    if not session_token:
        error("Login succeeded but no session token was returned.")
        return 1

    # Persist secure session token (not raw password/Basic credentials).
    cfg["username"] = username
    cfg["token"] = session_token
    save_config(cfg)

    ok(f"Logged in as [bold]{username}[/bold]")
    return 0


def cmd_logout(args) -> int:
    cfg = load_config()
    changed = False

    # Best-effort server-side logout for cookie/session invalidation.
    try:
        get_client().post("/auth/logout")
    except Exception:
        pass

    if cfg.get("username"):
        cfg["username"] = ""
        changed = True
    if cfg.get("token"):
        cfg["token"] = ""
        changed = True

    if changed:
        save_config(cfg)
        ok("Logged out. Session token removed.")
    else:
        warn("Not logged in.")
    return 0


def cmd_whoami(args) -> int:
    username = get_username_from_config()
    cfg = load_config()

    if not username and not cfg.get("token"):
        warn("Not logged in. Run: upcode-harbor auth login")
        return 1

    header("Current Session")
    data = {
        "user":    username if username else "(api-key)",
        "api_url": cfg.get("api_url", ""),
        "auth":    "Bearer" if cfg.get("token") else "none",
    }
    kv(data, indent=2)

    # Verify session is still valid
    try:
        get_client().get("/")
        ok("Session is active.")
    except APIError as e:
        if e.status == 401:
            warn("Session expired or invalid. Run: upcode-harbor auth login")
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
    login_p.add_argument("--totp", metavar="CODE", help="TOTP code (unsafe – prefer interactive prompt)")

    sp.add_parser("logout", help="Remove stored session token")
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
