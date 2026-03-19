"""SQLite-backed repo graph with in-memory adjacency maps for fast queries."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from typing import Protocol

import structlog

from rkp.core.models import ModuleEdge

logger = structlog.get_logger()


class RepoGraph(Protocol):
    """Protocol for module dependency graph operations."""

    def add_edge(self, source: str, target: str, edge_type: str, repo_id: str) -> None: ...
    def get_dependencies(self, module: str) -> list[str]: ...
    def get_dependents(self, module: str) -> list[str]: ...
    def get_test_locations(self, module: str) -> list[str]: ...
    def path_to_module(self, path: str) -> str | None: ...
    def get_modules(self) -> list[str]: ...
    def clear(self, repo_id: str) -> None: ...


class SqliteRepoGraph:
    """SQLite edges + in-memory adjacency maps for fast traversal.

    Stores edges in the module_edges table (from M1 schema).
    On construction, loads existing edges into in-memory maps.
    add_edge writes to both SQLite and in-memory maps.
    """

    def __init__(self, db: sqlite3.Connection, *, repo_id: str = "", branch: str = "main") -> None:
        self._db = db
        self._repo_id = repo_id
        self._branch = branch

        # In-memory adjacency maps: edge_type -> source -> set[target]
        self._forward: dict[str, defaultdict[str, set[str]]] = {
            "imports": defaultdict(set),
            "contains": defaultdict(set),
            "tests": defaultdict(set),
        }
        # Reverse map: target -> set[source] for "imports" edges
        self._reverse_imports: defaultdict[str, set[str]] = defaultdict(set)
        # All known modules
        self._modules: set[str] = set()

        self._load_from_db()

    def _load_from_db(self) -> None:
        """Load existing edges from SQLite into in-memory maps."""
        conditions = ["1=1"]
        params: list[str] = []
        if self._repo_id:
            conditions.append("repo_id = ?")
            params.append(self._repo_id)

        query = f"SELECT source_path, target_path, edge_type FROM module_edges WHERE {' AND '.join(conditions)}"
        rows = self._db.execute(query, params).fetchall()
        for row in rows:
            source = str(row["source_path"])
            target = str(row["target_path"])
            edge_type = str(row["edge_type"])
            self._add_to_memory(source, target, edge_type)

    def _add_to_memory(self, source: str, target: str, edge_type: str) -> None:
        """Add an edge to in-memory maps."""
        if edge_type not in self._forward:
            self._forward[edge_type] = defaultdict(set)
        self._forward[edge_type][source].add(target)
        self._modules.add(source)
        self._modules.add(target)
        if edge_type == "imports":
            self._reverse_imports[target].add(source)

    def add_edge(self, source: str, target: str, edge_type: str, repo_id: str) -> None:
        """Add an edge to both SQLite and in-memory maps."""
        self._db.execute(
            """INSERT OR IGNORE INTO module_edges (source_path, target_path, edge_type, repo_id, branch)
               VALUES (?, ?, ?, ?, ?)""",
            (source, target, edge_type, repo_id or self._repo_id, self._branch),
        )
        self._db.commit()
        self._add_to_memory(source, target, edge_type)

    def get_dependencies(self, module: str) -> list[str]:
        """What does this module import?"""
        return sorted(self._forward["imports"].get(module, set()))

    def get_dependents(self, module: str) -> list[str]:
        """What imports this module?"""
        return sorted(self._reverse_imports.get(module, set()))

    def get_test_locations(self, module: str) -> list[str]:
        """Where are tests for this module?"""
        return sorted(self._forward["tests"].get(module, set()))

    def path_to_module(self, path: str) -> str | None:
        """Which module owns this path? Longest prefix match."""
        normalized = path.replace("\\", "/")
        best_match: str | None = None
        best_length = 0
        for mod in self._modules:
            mod_normalized = mod.replace("\\", "/")
            if normalized.startswith(mod_normalized) and len(mod_normalized) > best_length:
                best_match = mod
                best_length = len(mod_normalized)
        return best_match

    def get_modules(self) -> list[str]:
        """All detected modules."""
        return sorted(self._modules)

    def clear(self, repo_id: str) -> None:
        """Remove all edges for a repo_id."""
        self._db.execute("DELETE FROM module_edges WHERE repo_id = ?", (repo_id,))
        self._db.commit()
        # Rebuild in-memory maps
        self._forward = {
            "imports": defaultdict(set),
            "contains": defaultdict(set),
            "tests": defaultdict(set),
        }
        self._reverse_imports = defaultdict(set)
        self._modules = set()
        self._load_from_db()

    def to_edges(self) -> list[ModuleEdge]:
        """Export all in-memory edges as ModuleEdge dataclass instances."""
        return [
            ModuleEdge(
                source_path=source,
                target_path=target,
                edge_type=edge_type,
                repo_id=self._repo_id,
                branch=self._branch,
            )
            for edge_type, adj in self._forward.items()
            for source, targets in adj.items()
            for target in targets
        ]

    def register_module(self, module: str) -> None:
        """Register a module path without any edges (for isolated modules)."""
        self._modules.add(module)
