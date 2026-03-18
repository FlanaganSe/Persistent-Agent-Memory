"""CLI application entry point. Commands added in M2+."""

from __future__ import annotations

import typer

app = typer.Typer(rich_markup_mode="rich", no_args_is_help=True)


@app.callback()
def callback() -> None:
    """Repo Knowledge Plane — portable, verified repo context for every coding agent."""


def main() -> None:
    """CLI entry point."""
    app()
