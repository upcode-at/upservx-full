"""
upservx logs – view Upcode Harbor platform logs.

Commands:
  upservx logs show [--lines N] [--raw]
  upservx logs follow [--raw]
"""

import json
import subprocess
import sys

from cli.output import error, header, info

LOG_FILE = "/var/log/upservx/activity.log"


def _format_log_line(line: str, raw: bool = False) -> str:
    """Format one log line for terminal output.

    If a line is JSON, convert common fields into a concise readable line.
    """
    if raw:
        return line.rstrip("\n")

    text = line.rstrip("\n")
    if not text:
        return ""

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text

    if not isinstance(payload, dict):
        return text

    ts = payload.get("timestamp") or payload.get("time") or payload.get("ts") or payload.get("@timestamp")
    level = payload.get("level") or payload.get("severity")
    tag = payload.get("tag") or payload.get("module") or payload.get("component") or payload.get("source")
    msg = payload.get("message") or payload.get("msg") or payload.get("event") or payload.get("detail")

    parts = []
    if ts:
        parts.append(str(ts))
    if level:
        parts.append(f"[{str(level).upper()}]")
    if tag:
        parts.append(f"[{tag}]")
    if msg:
        parts.append(str(msg))

    if parts:
        return " ".join(parts)

    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def cmd_show(args) -> int:
    header(f"Upcode Harbor Logs (last {args.lines} lines)")
    try:
        result = subprocess.run(
            ["tail", "-n", str(args.lines), LOG_FILE],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            error(f"Cannot read log file: {result.stderr.strip()}")
            return 1

        for line in result.stdout.splitlines():
            formatted = _format_log_line(line, raw=args.raw)
            if formatted:
                print(formatted)
    except FileNotFoundError:
        error(f"Log file not found: {LOG_FILE}")
        return 1
    return 0


def cmd_follow(args) -> int:
    info(f"Following {LOG_FILE}  (Ctrl+C to stop)")
    proc = None
    try:
        proc = subprocess.Popen(
            ["tail", "-f", LOG_FILE],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        assert proc.stdout is not None
        for line in proc.stdout:
            formatted = _format_log_line(line, raw=args.raw)
            if formatted:
                print(formatted)
    except KeyboardInterrupt:
        print()
    except FileNotFoundError:
        error(f"Log file not found: {LOG_FILE}")
        return 1
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
    return 0


def register(subparsers):
    p = subparsers.add_parser("logs", help="View Upcode Harbor logs")
    sp = p.add_subparsers(dest="logs_cmd", metavar="<action>")
    sp.required = True

    show_p = sp.add_parser("show", help="Show recent log lines")
    show_p.add_argument("--lines", "-n", type=int, default=50, metavar="N", help="Number of lines (default: 50)")
    show_p.add_argument("--raw", action="store_true", help="Print raw log lines without formatting")

    follow_p = sp.add_parser("follow", help="Follow the log in real-time")
    follow_p.add_argument("--raw", action="store_true", help="Print raw log lines without formatting")

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
