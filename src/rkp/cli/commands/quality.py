"""rkp quality — run the full quality harness."""

from __future__ import annotations

from pathlib import Path

import typer

from rkp.cli.app import AppState


def quality(
    ctx: typer.Context,
    fixtures: Path = typer.Option(
        Path("tests/fixtures"),
        help="Path to fixture repos directory",
    ),
    report: Path | None = typer.Option(
        None,
        help="Path to write JSON report",
    ),
    skip_performance: bool = typer.Option(
        False,
        "--skip-performance",
        help="Skip the 250k LOC performance benchmark",
    ),
) -> None:
    """Run the full quality harness: extraction, conformance, leakage, drift, performance."""
    from rkp.quality.harness import run_quality_harness

    state: AppState = ctx.obj

    fixtures_path = fixtures
    if not fixtures_path.is_absolute():
        fixtures_path = state.repo_path / fixtures_path

    result = run_quality_harness(
        fixtures_path,
        report,
        skip_performance=skip_performance,
    )

    if not result.overall_pass:
        raise typer.Exit(code=1)
