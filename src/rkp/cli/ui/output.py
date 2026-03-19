"""CLI output utilities: console routing, JSON, colored messages."""

from __future__ import annotations

import json
import sys
from typing import Any

from rich.console import Console

# Diagnostic output goes to stderr (keeps stdout clean for MCP/data).
console = Console(stderr=True)

# Data output (JSON, previews) goes to stdout.
data_console = Console()


def print_json(data: Any) -> None:
    """Write structured JSON to stdout."""
    sys.stdout.write(json.dumps(data, indent=2, default=str) + "\n")


def print_error(msg: str) -> None:
    """Print an error message to stderr in red."""
    console.print(f"[red]{msg}[/red]")


def print_warning(msg: str) -> None:
    """Print a warning to stderr in yellow."""
    console.print(f"[yellow]{msg}[/yellow]")


def print_success(msg: str) -> None:
    """Print a success message to stderr in green."""
    console.print(f"[green]{msg}[/green]")


def print_info(msg: str) -> None:
    """Print an informational message to stderr."""
    console.print(f"[dim]{msg}[/dim]")
