"""
upservx logs – view UpservX platform logs.

Commands:
  upservx logs show [--lines N]
  upservx logs follow
"""

import subprocess
import sys

from cli.output import error, header, info

LOG_FILE = "/etc/upservx.log"


def cmd_show(args) -> int:
    header(f"UpservX Logs (last {args.lines} lines)")
    try:
        result = subprocess.run(
            ["tail", "-n", str(args.lines), LOG_FILE],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            error(f"Cannot read log file: {result.stderr.strip()}")
            return 1
        print(result.stdout)
    except FileNotFoundError:
        error(f"Log file not found: {LOG_FILE}")
        return 1
    return 0


def cmd_follow(args) -> int:
    info(f"Following {LOG_FILE}  (Ctrl+C to stop)")
    try:
        subprocess.run(["tail", "-f", LOG_FILE])
    except KeyboardInterrupt:
        print()
    except FileNotFoundError:
        error(f"Log file not found: {LOG_FILE}")
        return 1
    return 0


def register(subparsers):
    p = subparsers.add_parser("logs", help="View UpservX logs")
    sp = p.add_subparsers(dest="logs_cmd", metavar="<action>")
    sp.required = True

    show_p = sp.add_parser("show", help="Show recent log lines")
    show_p.add_argument("--lines", "-n", type=int, default=50, metavar="N", help="Number of lines (default: 50)")

    sp.add_parser("follow", help="Follow the log in real-time")

    p.set_defaults(func=_dispatch)


def _dispatch(args) -> int:
    dispatch = {
        "show": cmd_show,
        "follow": cmd_follow,
    }
    handler = dispatch.get(args.logs_cmd)
    if handler:
        return handler(args)
    return 1
