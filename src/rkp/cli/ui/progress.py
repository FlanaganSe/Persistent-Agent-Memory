"""Progress indicators for CLI operations."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from rkp.cli.ui.output import console


@contextmanager
def extraction_progress(total_files: int) -> Iterator[Progress]:
    """Context manager for extraction progress.

    Uses a spinner + X/Y counter on stderr.
    """
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]Extracting"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    )
    with progress:
        yield progress


def track_items[T](items: list[T], description: str = "Processing") -> Iterator[T]:
    """Track progress over a list of items on stderr."""
    progress = Progress(
        SpinnerColumn(),
        TextColumn(f"[bold blue]{description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
    )
    with progress:
        task = progress.add_task(description, total=len(items))
        for item in items:
            yield item
            progress.advance(task)
