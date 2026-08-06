"""
upcode-harbor service – manage the Upcode Harbor systemd service.

Commands:
  upcode-harbor service status
  upcode-harbor service start
  upcode-harbor service stop
  upcode-harbor service restart
"""

import subprocess

from cli.output import error, header, info, kv, ok, warn

SERVICE = "upcode-harbor"


def _systemctl(action: str) -> tuple[int, str]:
    result = subprocess.run(
        ["systemctl", action, SERVICE],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout + result.stderr


def cmd_status(args) -> int:
    header("Upcode Harbor Service Status")
    rc, out = _systemctl("status")
    print(out)
    return 0


def cmd_start(args) -> int:
    info("Starting Upcode Harbor service...")
    rc, out = _systemctl("start")
    if rc == 0:
        ok("Service started.")
    else:
        error("Failed to start service.")
        print(out)
    return rc


def cmd_stop(args) -> int:
    info("Stopping Upcode Harbor service...")
    rc, out = _systemctl("stop")
    if rc == 0:
        ok("Service stopped.")
    else:
        error("Failed to stop service.")
        print(out)
    return rc


def cmd_restart(args) -> int:
    info("Restarting Upcode Harbor service...")
    rc, out = _systemctl("restart")
    if rc == 0:
        ok("Service restarted.")
    else:
        error("Failed to restart service.")
        print(out)
    return rc


def register(subparsers):
    p = subparsers.add_parser("service", help="Manage the Upcode Harbor system service")
    sp = p.add_subparsers(dest="service_cmd", metavar="<action>")
    sp.required = True

    sp.add_parser("status", help="Show service status")
    sp.add_parser("start", help="Start the service")
    sp.add_parser("stop", help="Stop the service")
    sp.add_parser("restart", help="Restart the service")

    p.set_defaults(func=_dispatch)


def _dispatch(args) -> int:
    dispatch = {
        "status": cmd_status,
        "start": cmd_start,
        "stop": cmd_stop,
        "restart": cmd_restart,
    }
    handler = dispatch.get(args.service_cmd)
    if handler:
        return handler(args)
    return 1
