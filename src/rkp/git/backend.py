"""GitBackend Protocol — interface for git operations."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class GitBackend(Protocol):
    """Protocol for git backend operations.

    Phase 1: Git CLI implementation (default).
    Phase 2: Optional pygit2 accelerator.
    """

    def repo_root(self) -> Path: ...

    def head(self) -> str: ...

    def current_branch(self) -> str: ...

    def worktree_id(self) -> str: ...

    def list_tracked_files(self) -> list[Path]: ...

    def list_untracked_files(self) -> list[Path]: ...

    def file_hash(self, path: Path) -> str: ...

    def diff_status(self) -> list[tuple[str, Path]]: ...

    def changed_files_between(self, old_ref: str, new_ref: str) -> set[str]: ...

    def is_dirty(self) -> bool: ...
