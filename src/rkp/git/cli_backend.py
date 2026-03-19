"""Git CLI backend — subprocess-based git operations."""

from __future__ import annotations

import subprocess
from pathlib import Path

import structlog

from rkp.core.errors import RkpError

logger = structlog.get_logger()

_DEFAULT_TIMEOUT = 10


class GitError(RkpError):
    """Raised when a git operation fails."""

    def __init__(self, command: str, message: str) -> None:
        self.command = command
        super().__init__(f"git {command}: {message}")


class NotAGitRepoError(GitError):
    """Raised when the path is not inside a git repository."""

    def __init__(self, path: Path) -> None:
        super().__init__("rev-parse", f"not a git repository: {path}")


class CliGitBackend:
    """Git CLI implementation of GitBackend Protocol."""

    def __init__(self, path: Path) -> None:
        self._root = self._resolve_root(path)

    def _run(
        self, *args: str, timeout: int = _DEFAULT_TIMEOUT
    ) -> subprocess.CompletedProcess[str]:
        """Run a git command and return the result."""
        return subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            check=False,
            cwd=self._root,
            timeout=timeout,
        )

    @staticmethod
    def _resolve_root(path: Path) -> Path:
        """Resolve the git repo root from a path."""
        resolved = path.resolve()
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
            cwd=resolved if resolved.is_dir() else resolved.parent,
            timeout=_DEFAULT_TIMEOUT,
        )
        if result.returncode != 0:
            raise NotAGitRepoError(path)
        return Path(result.stdout.strip())

    def repo_root(self) -> Path:
        """Return the resolved repository root."""
        return self._root

    def head(self) -> str:
        """Return the HEAD commit SHA."""
        result = self._run("rev-parse", "HEAD")
        if result.returncode != 0:
            # Empty repo (no commits)
            return ""
        return result.stdout.strip()

    def current_branch(self) -> str:
        """Return the current branch name, or 'HEAD' if detached."""
        result = self._run("rev-parse", "--abbrev-ref", "HEAD")
        if result.returncode != 0:
            return ""
        return result.stdout.strip()

    def worktree_id(self) -> str:
        """Return a stable worktree identifier (resolved repo root path)."""
        return str(self._root)

    def list_tracked_files(self) -> list[Path]:
        """Return tracked files relative to repo root."""
        result = self._run("ls-files")
        if result.returncode != 0:
            logger.warning("git ls-files failed", stderr=result.stderr.strip())
            return []
        return [Path(line) for line in result.stdout.strip().splitlines() if line]

    def list_untracked_files(self) -> list[Path]:
        """Return untracked (but not ignored) files relative to repo root."""
        result = self._run("ls-files", "--others", "--exclude-standard")
        if result.returncode != 0:
            logger.warning("git ls-files --others failed", stderr=result.stderr.strip())
            return []
        return [Path(line) for line in result.stdout.strip().splitlines() if line]

    def file_hash(self, path: Path) -> str:
        """Return the git blob OID (SHA-1 hash) for a file."""
        result = self._run("hash-object", "--", str(path))
        if result.returncode != 0:
            logger.warning("git hash-object failed", path=str(path), stderr=result.stderr.strip())
            return ""
        return result.stdout.strip()

    def diff_status(self) -> list[tuple[str, Path]]:
        """Return staged+unstaged changes as (status, path) pairs."""
        result = self._run("diff", "--name-status", "HEAD")
        if result.returncode != 0:
            # Could be empty repo
            return []
        pairs: list[tuple[str, Path]] = []
        for line in result.stdout.strip().splitlines():
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) == 2:
                pairs.append((parts[0], Path(parts[1])))
        return pairs

    def is_dirty(self) -> bool:
        """Return True if the working tree has uncommitted changes."""
        result = self._run("status", "--porcelain")
        if result.returncode != 0:
            return False
        return bool(result.stdout.strip())
