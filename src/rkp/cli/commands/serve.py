"""rkp serve — start the MCP server."""

from __future__ import annotations

import sys

import typer

from rkp.cli.app import AppState
from rkp.cli.ui.output import console, print_error


def serve(
    ctx: typer.Context,
) -> None:
    """Start the MCP server (stdio transport)."""
    state: AppState = ctx.obj

    try:
        # Check if database exists; if not, auto-extract.
        if not state.db_path.exists():
            if not state.quiet:
                console.print(
                    "[yellow]No index found. Running extraction before serving...[/yellow]",
                )
            db = state.ensure_db()
            from rkp.indexer.orchestrator import run_extraction
            from rkp.store.claims import SqliteClaimStore

            claim_store = SqliteClaimStore(db)
            repo_id = str(state.repo_path)
            summary = run_extraction(
                state.repo_path,
                claim_store,
                repo_id=repo_id,
                git_backend=state.ensure_git(),
            )
            if not state.quiet:
                console.print(
                    f"[dim]Extracted {summary.claims_created} claims from "
                    f"{summary.files_parsed} files[/dim]"
                )
            if state.db is not None:
                state.db.close()
                state.db = None

        # Count claims for startup message
        claim_count = 0
        if state.db_path.exists():
            import sqlite3

            try:
                conn = sqlite3.connect(str(state.db_path))
                row = conn.execute("SELECT COUNT(*) FROM claims").fetchone()
                claim_count = row[0] if row else 0
                conn.close()
            except sqlite3.Error:
                pass

        if not state.quiet:
            console.print(
                f"RKP MCP server starting (repo: {state.repo_path}, {claim_count} claims indexed)"
            )

        # Build a server that uses the correct paths from AppState.
        from rkp.server.mcp import create_server_for_path

        server = create_server_for_path(
            repo_root=state.repo_path,
            db_path=state.db_path,
        )
        server.run()

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        # Clean shutdown on Ctrl+C.
        if not state.quiet:
            print("\nServer stopped.", file=sys.stderr)
        raise typer.Exit(code=130) from None
    except Exception as exc:
        print_error(f"Server failed: {exc}")
        if state.verbose > 0:
            console.print_exception()
        raise typer.Exit(code=2) from exc
