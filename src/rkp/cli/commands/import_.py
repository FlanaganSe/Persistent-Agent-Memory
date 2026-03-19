"""rkp import — ingest existing instruction files as governed claims."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from rkp.cli.app import AppState
from rkp.cli.ui.output import (
    console,
    print_error,
    print_info,
    print_json,
    print_warning,
)


def import_files(
    ctx: typer.Context,
    source: str | None = typer.Option(
        None, "--source", help="Import a specific file instead of auto-discovering"
    ),
    take_ownership: bool = typer.Option(
        False, "--take-ownership", help="Set managed-by-rkp instead of imported-human-owned"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be imported without importing"
    ),
) -> None:
    """Import existing instruction files (AGENTS.md, CLAUDE.md, etc.) as claims."""
    state: AppState = ctx.obj
    repo_path = state.repo_path

    try:
        db = state.ensure_db()

        from rkp.importer.engine import run_import
        from rkp.store.artifacts import SqliteArtifactStore
        from rkp.store.claims import SqliteClaimStore

        claim_store = SqliteClaimStore(db)
        artifact_store = SqliteArtifactStore(db)
        repo_id = str(repo_path)

        git_backend = state.ensure_git()
        branch = git_backend.current_branch() if git_backend else "main"

        source_path = Path(source).resolve() if source else None

        # Suppress structlog in JSON/quiet mode
        if state.json_output or state.quiet:
            import logging

            logging.getLogger().setLevel(logging.CRITICAL)

        if not state.quiet and not state.json_output:
            if source_path:
                print_info(f"Importing from {source_path}...")
            else:
                print_info("Discovering instruction files...")

        result = run_import(
            repo_path,
            claim_store,
            repo_id=repo_id,
            branch=branch,
            source_path=source_path,
            take_ownership=take_ownership,
            dry_run=dry_run,
            artifact_store=artifact_store,
        )

        if state.json_output:
            print_json(
                {
                    "status": "dry_run" if dry_run else "success",
                    "files_discovered": list(result.files_discovered),
                    "files_parsed": list(result.files_parsed),
                    "claims_created": result.claims_created,
                    "claims_deduplicated": result.claims_deduplicated,
                    "conflicts_found": result.conflicts_found,
                    "unparseable_sections": [
                        {"heading": u.heading, "content": u.content[:200], "reason": u.reason}
                        for u in result.unparseable_sections
                    ],
                    "security_warnings": list(result.security_warnings),
                    "warnings": list(result.warnings),
                }
            )
        elif not state.quiet:
            # Show discovered files
            if result.files_discovered:
                console.print("\n[bold]Discovered instruction files:[/bold]")
                for fp in result.files_discovered:
                    console.print(f"  {fp}")

            if not result.files_discovered:
                print_info(
                    "No instruction files found. "
                    "Looking for: AGENTS.md, CLAUDE.md, .github/copilot-instructions.md, "
                    ".github/workflows/copilot-setup-steps.yml, .cursor/rules"
                )
                raise typer.Exit(code=0)

            # Summary table
            if result.files_parsed:
                console.print()
                table = Table(title="Import Results", show_lines=True)
                table.add_column("Source", style="cyan")
                table.add_column("Claims", justify="right")
                table.add_column("Warnings", justify="right")

                # Group by file
                for fp in result.files_parsed:
                    # Count claims for this file (approximate: we don't track per-file)
                    name = Path(fp).name
                    table.add_row(name, "—", "—")

                table.add_section()
                table.add_row(
                    "[bold]Total[/bold]",
                    f"[bold]{result.claims_created}[/bold]",
                    f"[bold]{len(result.warnings)}[/bold]",
                )
                console.print(table)

            # Summary line
            console.print(
                f"\n{result.claims_created} claims imported"
                f" ({result.claims_deduplicated} deduplicated"
                f", {result.conflicts_found} conflicts"
                f", {len(result.warnings)} warnings)"
            )

            if result.unparseable_sections:
                console.print(
                    f"\n[yellow]{len(result.unparseable_sections)} section(s) could not be parsed "
                    f"(generic prose, overview content)[/yellow]"
                )
                if state.verbose > 0:
                    for section in result.unparseable_sections:
                        console.print(f"  [{section.heading}]: {section.reason}")

            if result.security_warnings:
                console.print()
                for w in result.security_warnings:
                    print_warning(w)

            if dry_run:
                console.print("\n[dim]Dry run — no changes persisted.[/dim]")
            else:
                ownership_label = "managed-by-rkp" if take_ownership else "imported-human-owned"
                console.print(
                    "\nImported claims are marked as [yellow]imported-unreviewed[/yellow] "
                    "(lower authority than build/test evidence). "
                    "Run [bold]rkp review[/bold] to promote them."
                )
                console.print(f"Imported files tracked as [cyan]{ownership_label}[/cyan].")

        if result.conflicts_found > 0:
            raise typer.Exit(code=1)
        raise typer.Exit(code=0)

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        raise typer.Exit(code=130) from None
    except Exception as exc:
        print_error(f"Import failed: {exc}")
        if state.verbose > 0:
            console.print_exception()
        raise typer.Exit(code=2) from exc
