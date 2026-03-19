"""rkp preview — show projected instruction artifact without writing."""

from __future__ import annotations

import json
import sys

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from rkp.cli.app import AppState
from rkp.indexer.orchestrator import run_extraction
from rkp.projection.adapters.agents_md import AgentsMdAdapter
from rkp.projection.adapters.claude_md import ClaudeMdAdapter
from rkp.projection.capability_matrix import get_capability
from rkp.projection.engine import ProjectionPolicy, project
from rkp.store.claims import SqliteClaimStore

console = Console(stderr=True)


def preview(
    ctx: typer.Context,
    host: str = typer.Option("codex", help="Target host (codex, agents-md, claude)"),
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

    # Select adapter
    adapter = ClaudeMdAdapter() if host == "claude" else AgentsMdAdapter()

    policy = ProjectionPolicy()
    result = project(claims, adapter, capability, policy)

    # Output
    files = result.adapter_result.files

    if state.json_output:
        output = {
            "host": host,
            "files": files,
            "excluded_sensitive": result.excluded_sensitive,
            "excluded_low_confidence": result.excluded_low_confidence,
            "overflow_report": result.adapter_result.overflow_report,
        }
        sys.stdout.write(json.dumps(output, indent=2) + "\n")
    elif host == "claude":
        _display_claude_output(files)
    else:
        content = files.get("AGENTS.md", "")
        sys.stdout.write(content)


def _display_claude_output(files: dict[str, str]) -> None:
    """Display multi-file Claude output with Rich panels."""
    out = Console()

    # CLAUDE.md
    claude_md = files.get("CLAUDE.md", "")
    if claude_md:
        out.print(Panel(claude_md, title="CLAUDE.md", border_style="green"))

    # .claude/rules/ files
    rule_files = {k: v for k, v in sorted(files.items()) if k.startswith(".claude/rules/")}
    for path, content in rule_files.items():
        out.print(Panel(content, title=path, border_style="blue"))

    # .claude/skills/ files
    skill_files = {k: v for k, v in sorted(files.items()) if k.startswith(".claude/skills/")}
    for path, content in skill_files.items():
        out.print(Panel(content, title=path, border_style="cyan"))

    # Settings snippet
    settings = files.get(".claude/settings-snippet.json", "")
    if settings:
        syntax = Syntax(settings, "json", theme="monokai")
        out.print(Panel(syntax, title=".claude/settings-snippet.json", border_style="yellow"))
