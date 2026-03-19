"""CLI application entry point with composition root."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import typer

from rkp.store.database import open_database, run_migrations

app = typer.Typer(rich_markup_mode="rich", no_args_is_help=True)


@dataclass
class AppState:
    """Shared state for CLI commands."""

    repo_root: Path
    db: sqlite3.Connection
    json_output: bool = False
    verbose: bool = False


@app.callback()
def callback(
    ctx: typer.Context,
    repo: str = typer.Option(".", envvar="RKP_REPO", help="Repository root path"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Quiet output"),
) -> None:
    """Repo Knowledge Plane — portable, verified repo context for every coding agent."""
    repo_path = Path(repo).resolve()
    db_path = repo_path / ".rkp" / "local" / "rkp.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = open_database(db_path)
    run_migrations(db)
    ctx.obj = AppState(
        repo_root=repo_path,
        db=db,
        json_output=json_output,
        verbose=verbose,
    )


# Import and register subcommands
from rkp.cli.commands.preview import preview  # noqa: E402
from rkp.cli.commands.serve import serve  # noqa: E402

app.command()(preview)
app.command()(serve)


def main() -> None:
    """CLI entry point."""
    app()
