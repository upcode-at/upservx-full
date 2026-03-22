"""
Terminal output helpers – powered by rich.
"""

import sys

from rich.console import Console
from rich.table import Table
from rich import print as rprint

console = Console()
err_console = Console(stderr=True)

# Keep bare color constants for legacy compat (used in main.py banner)
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def _c(color: str, text: str) -> str:
    """Legacy helper – still used in a few places."""
    if not sys.stdout.isatty():
        return text
    return f"{color}{text}{RESET}"


def ok(msg: str) -> None:
    console.print(f"[bold green]✔[/bold green] {msg}")


def warn(msg: str) -> None:
    console.print(f"[bold yellow]⚠[/bold yellow]  {msg}")


def error(msg: str) -> None:
    err_console.print(f"[bold red]✖[/bold red] {msg}")


def info(msg: str) -> None:
    console.print(f"[cyan]  {msg}[/cyan]")


def header(msg: str) -> None:
    console.print()
    console.rule(f"[bold]{msg}[/bold]")


def table(rows: list[dict], columns: list[str]) -> None:
    """Print a rich table from a list of dicts."""
    t = Table(show_header=True, header_style="bold")
    for col in columns:
        t.add_column(col.upper())
    for row in rows:
        t.add_row(*[str(row.get(col, "")) for col in columns])
    console.print(t)
    console.print()


def kv(data: dict, indent: int = 0) -> None:
    """Print key-value pairs."""
    pad = " " * indent
    for key, value in data.items():
        console.print(f"{pad}[bold]{key}:[/bold] {value}")
