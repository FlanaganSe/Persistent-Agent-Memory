"""Unit tests for the Git CLI backend."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from rkp.git.cli_backend import CliGitBackend, NotAGitRepoError


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository with one commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True, check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=repo, capture_output=True, check=True
    )
    (repo / "hello.py").write_text("print('hello')\n")
    subprocess.run(["git", "add", "hello.py"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True, check=True)
    return repo


@pytest.fixture
def empty_git_repo(tmp_path: Path) -> Path:
    """Create a git repo with no commits."""
    repo = tmp_path / "empty"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    return repo


class TestCliGitBackend:
    def test_repo_root(self, git_repo: Path) -> None:
        backend = CliGitBackend(git_repo)
        assert backend.repo_root() == git_repo.resolve()

    def test_head(self, git_repo: Path) -> None:
        backend = CliGitBackend(git_repo)
        head = backend.head()
        assert len(head) == 40  # SHA-1 hex
        assert all(c in "0123456789abcdef" for c in head)

    def test_current_branch(self, git_repo: Path) -> None:
        backend = CliGitBackend(git_repo)
        # Default branch varies (main or master), just check it's non-empty
        branch = backend.current_branch()
        assert branch in ("main", "master")

    def test_list_tracked_files(self, git_repo: Path) -> None:
        backend = CliGitBackend(git_repo)
        files = backend.list_tracked_files()
        assert Path("hello.py") in files

    def test_file_hash(self, git_repo: Path) -> None:
        backend = CliGitBackend(git_repo)
        h = backend.file_hash(Path("hello.py"))
        assert len(h) == 40

    def test_is_dirty_clean(self, git_repo: Path) -> None:
        backend = CliGitBackend(git_repo)
        assert not backend.is_dirty()

    def test_is_dirty_modified(self, git_repo: Path) -> None:
        (git_repo / "hello.py").write_text("print('changed')\n")
        backend = CliGitBackend(git_repo)
        assert backend.is_dirty()

    def test_list_untracked_files(self, git_repo: Path) -> None:
        (git_repo / "new_file.py").write_text("# new\n")
        backend = CliGitBackend(git_repo)
        untracked = backend.list_untracked_files()
        assert Path("new_file.py") in untracked

    def test_worktree_id(self, git_repo: Path) -> None:
        backend = CliGitBackend(git_repo)
        wt = backend.worktree_id()
        assert str(git_repo.resolve()) == wt

    def test_not_a_git_repo(self, tmp_path: Path) -> None:
        non_repo = tmp_path / "not_git"
        non_repo.mkdir()
        with pytest.raises(NotAGitRepoError):
            CliGitBackend(non_repo)

    def test_empty_repo_head(self, empty_git_repo: Path) -> None:
        backend = CliGitBackend(empty_git_repo)
        assert backend.head() == ""

    def test_diff_status(self, git_repo: Path) -> None:
        (git_repo / "hello.py").write_text("print('changed')\n")
        backend = CliGitBackend(git_repo)
        diff = backend.diff_status()
        assert len(diff) >= 1
        statuses = [s for s, _ in diff]
        assert "M" in statuses
