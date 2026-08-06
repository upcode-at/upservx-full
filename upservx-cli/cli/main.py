"""
upservx CLI – main entry point and argument parsing.
"""

import argparse
import sys

from cli.output import BOLD, CYAN, GREEN, RESET, _c

from cli.commands import apps, auth, backup, containers, logs, service, system

VERSION = "0.7.0"

BANNER = r"""
  _   _       __                     __  __
 | | | |_ __ / _\ ___ _ ____   ____  \ \/ /
 | | | | '_ \\ \ / _ \ '__\ \ / / \ \/\/ /
 | |_| | |_) |\ \  __/ |   \ V /   >  <
  \___/| .__/ \__/\___|_|    \_/   /_/\_\
       |_|
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="upservx",
        description="UpservX CLI – manage your server from the terminal.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  upservx auth login
  upservx auth whoami
  upservx service status
  upservx containers list
  upservx containers logs myapp --lines 200
  upservx system stats
  upservx apps list
  upservx apps install wordpress
  upservx backup create
  upservx logs show -n 100
  upservx logs follow
""",
    )

    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"upservx {VERSION}",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    subparsers.required = True

    # Register all commands
    auth.register(subparsers)
    service.register(subparsers)
    containers.register(subparsers)
    system.register(subparsers)
    logs.register(subparsers)
    apps.register(subparsers)
    backup.register(subparsers)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if hasattr(args, "func"):
        try:
            return args.func(args) or 0
        except KeyboardInterrupt:
            print()
            return 130
        except Exception as e:
            from cli.output import error
            error(str(e))
            return 1

    parser.print_help()
    return 0
