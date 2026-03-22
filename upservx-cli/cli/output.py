"""
Terminal output helpers – color, tables, banners.
"""

import sys

# ANSI colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

_NO_COLOR = not sys.stdout.isatty()


def _c(color: str, text: str) -> str:
    if _NO_COLOR:
        return text
    return f"{color}{text}{RESET}"


def ok(msg: str) -> None:
    print(_c(GREEN, "✔ ") + msg)


def warn(msg: str) -> None:
    print(_c(YELLOW, "⚠ ") + msg)


def error(msg: str) -> None:
    print(_c(RED, "✖ ") + msg, file=sys.stderr)


def info(msg: str) -> None:
    print(_c(CYAN, "  ") + msg)


def header(msg: str) -> None:
    print()
    print(_c(BOLD, msg))
    print(_c(DIM, "─" * len(msg)))


def table(rows: list[dict], columns: list[str]) -> None:
    """Print a fixed-width table from a list of dicts."""
    # Calculate column widths
    widths = {col: len(col) for col in columns}
    for row in rows:
        for col in columns:
            val = str(row.get(col, ""))
            widths[col] = max(widths[col], len(val))

    # Header row
    header_line = "  ".join(
        _c(BOLD, col.upper().ljust(widths[col])) for col in columns
    )
    print(header_line)
    print(_c(DIM, "  ".join("─" * widths[col] for col in columns)))

    # Data rows
    for row in rows:
        line = "  ".join(str(row.get(col, "")).ljust(widths[col]) for col in columns)
        print(line)

    print()


def kv(data: dict, indent: int = 0) -> None:
    """Print key-value pairs."""
    pad = " " * indent
    for key, value in data.items():
        print(f"{pad}{_c(BOLD, key + ':')} {value}")
