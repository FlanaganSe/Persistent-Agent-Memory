"""rkp preview — show projected instruction artifact without writing."""

from __future__ import annotations

import json
import sys

import typer
from rich.console import Console

from rkp.cli.app import AppState
from rkp.indexer.orchestrator import run_extraction
from rkp.projection.adapters.agents_md import AgentsMdAdapter
from rkp.projection.capability_matrix import get_capability
from rkp.projection.engine import ProjectionPolicy, project
from rkp.store.claims import SqliteClaimStore

console = Console(stderr=True)


def preview(
    ctx: typer.Context,
    host: str = typer.Option("codex", help="Target host (codex, agents-md)"),
) -> None:
    """Preview projected instruction artifact for a target host."""
    state: AppState = ctx.obj

    capability = get_capability(host)
    if capability is None:
        console.print(f"[red]Unsupported host: {host}[/red]")
        raise typer.Exit(code=2)

    # Run extraction if no claims exist
    claim_store = SqliteClaimStore(state.db)
    repo_id = str(state.repo_root)
    claims = claim_store.list_claims(repo_id=repo_id)
    if not claims:
        console.print("[dim]No claims found, running extraction...[/dim]")
        summary = run_extraction(
            state.repo_root,
            claim_store,
            repo_id=repo_id,
        )
        claims = claim_store.list_claims(repo_id=repo_id)
        if state.verbose:
            console.print(
                f"[dim]Extracted {summary.claims_created} claims from "
                f"{summary.files_parsed} files[/dim]"
            )

    # Project
    adapter = AgentsMdAdapter()
    policy = ProjectionPolicy()
    result = project(claims, adapter, capability, policy)

    # Output
    content = result.adapter_result.files.get("AGENTS.md", "")
    if state.json_output:
        output = {
            "host": host,
            "content": content,
            "excluded_sensitive": result.excluded_sensitive,
            "excluded_low_confidence": result.excluded_low_confidence,
            "overflow_report": result.adapter_result.overflow_report,
        }
        sys.stdout.write(json.dumps(output, indent=2) + "\n")
    else:
        sys.stdout.write(content)
