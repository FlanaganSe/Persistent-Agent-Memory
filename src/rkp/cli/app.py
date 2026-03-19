"""CLI application entry point with composition root."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

import typer

from rkp.core.config import RkpConfig
from rkp.git.backend import GitBackend

app = typer.Typer(rich_markup_mode="rich", no_args_is_help=True)


@dataclass
class AppState:
    """Shared state for CLI commands.

    Database and git backend are initialized lazily — commands decide
    what they need. doctor should work without a database; init creates
    one.
    """

    repo_path: Path
    db_path: Path
    db: sqlite3.Connection | None = None
    config: RkpConfig = field(default_factory=RkpConfig)
    git: GitBackend | None = None
    verbose: int = 0
    quiet: bool = False
    json_output: bool = False

    def ensure_db(self) -> sqlite3.Connection:
        """Open the database if not already open, running migrations."""
        if self.db is not None:
            return self.db
        from rkp.store.database import open_database, run_migrations

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = open_database(self.db_path)
        run_migrations(self.db)
        return self.db

    def ensure_git(self) -> GitBackend | None:
        """Try to create a git backend. Returns None if not a git repo."""
        if self.git is not None:
            return self.git
        from rkp.git.cli_backend import CliGitBackend, NotAGitRepoError

        try:
            self.git = CliGitBackend(self.repo_path)
            return self.git
        except NotAGitRepoError:
            return None

    def close(self) -> None:
        """Close database connection if open."""
        if self.db is not None:
            self.db.close()
            self.db = None


@app.callback()
def callback(
    ctx: typer.Context,
    repo: str = typer.Option(".", envvar="RKP_REPO", help="Repository root path"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    verbose: int = typer.Option(0, "--verbose", "-v", count=True, help="Verbosity level"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Quiet output"),
) -> None:
    """Repo Knowledge Plane — portable, verified repo context for every coding agent."""
    repo_path = Path(repo).resolve()
    db_path = repo_path / ".rkp" / "local" / "rkp.db"

    # quiet overrides verbose
    effective_verbose = 0 if quiet else min(verbose, 2)

    state = AppState(
        repo_path=repo_path,
        db_path=db_path,
        verbose=effective_verbose,
        quiet=quiet,
        json_output=json_output,
    )
    ctx.obj = state
    ctx.call_on_close(state.close)


# Import and register subcommands
from rkp.cli.commands.apply import apply  # noqa: E402
from rkp.cli.commands.doctor import doctor  # noqa: E402
from rkp.cli.commands.import_ import import_files  # noqa: E402
from rkp.cli.commands.init import init  # noqa: E402
from rkp.cli.commands.preview import preview  # noqa: E402
from rkp.cli.commands.purge import purge  # noqa: E402
from rkp.cli.commands.review import review  # noqa: E402
from rkp.cli.commands.serve import serve  # noqa: E402
from rkp.cli.commands.status import status  # noqa: E402

app.command()(init)
app.command()(preview)
app.command()(status)
app.command()(doctor)
app.command()(serve)
app.command()(review)
app.command(name="apply")(apply)
app.command()(purge)
app.command(name="import")(import_files)


def main() -> None:
    """CLI entry point."""
    try:
        app()
    except KeyboardInterrupt:
        raise typer.Exit(code=130) from None
