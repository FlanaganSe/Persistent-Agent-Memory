"""Module boundary extractor: package detection, import-based edges, test mapping."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import structlog

from rkp.core.types import SourceAuthority
from rkp.graph.repo_graph import SqliteRepoGraph
from rkp.indexer.parsers.javascript import ParsedJavaScriptFile
from rkp.indexer.parsers.python import ParsedPythonFile

logger = structlog.get_logger()

# Directories that are NOT modules (excluded from heuristic detection).
_EXCLUDED_DIRS = frozenset(
    {
        "tests",
        "test",
        "__tests__",
        "docs",
        "doc",
        "scripts",
        "script",
        ".github",
        ".vscode",
        ".idea",
        "node_modules",
        "vendor",
        "dist",
        "build",
        "out",
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        ".tox",
        ".nox",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        ".rkp",
        ".next",
        "coverage",
        "assets",
        "static",
        "public",
        "fixtures",
        "migrations",
    }
)

# Test directory names.
_TEST_DIR_NAMES = frozenset({"tests", "test", "__tests__"})


@dataclass(frozen=True)
class BoundaryClaimInput:
    """Structured input for building a module-boundary claim."""

    content: str
    source_authority: SourceAuthority
    scope: str
    confidence: float
    evidence_files: tuple[str, ...]


@dataclass(frozen=True)
class BoundaryResult:
    """Result of boundary extraction."""

    claims: tuple[BoundaryClaimInput, ...]
    modules_detected: int
    edges_created: int


def _detect_python_modules(repo_root: Path) -> list[tuple[str, str, tuple[str, ...]]]:
    """Detect Python packages (directories with __init__.py).

    Returns list of (module_dotted_name, module_path, evidence_files).
    Detects both src layout (src/pkg/) and flat layout (pkg/).
    """
    modules: list[tuple[str, str, tuple[str, ...]]] = []
    seen_paths: set[str] = set()

    # Look for __init__.py files
    for init_file in sorted(repo_root.rglob("__init__.py")):
        pkg_dir = init_file.parent
        rel_dir = pkg_dir.relative_to(repo_root)
        rel_str = str(rel_dir).replace("\\", "/")

        # Skip excluded directories
        if any(part in _EXCLUDED_DIRS for part in rel_dir.parts):
            continue

        if rel_str in seen_paths:
            continue
        seen_paths.add(rel_str)

        # Build dotted module name
        parts = list(rel_dir.parts)

        # For src layout, strip the "src" prefix from the dotted name
        dotted_parts = parts[1:] if parts and parts[0] == "src" else parts

        dotted_name = ".".join(dotted_parts) if dotted_parts else rel_str
        evidence = (str(rel_dir / "__init__.py"),)

        modules.append((dotted_name, rel_str, evidence))

    return modules


def _detect_js_modules(repo_root: Path) -> list[tuple[str, str, tuple[str, ...]]]:
    """Detect JS/TS modules (directories with index.ts/index.js or package.json workspaces).

    Returns list of (module_name, module_path, evidence_files).
    """
    modules: list[tuple[str, str, tuple[str, ...]]] = []
    seen_paths: set[str] = set()

    index_names = ("index.ts", "index.js", "index.tsx", "index.jsx")

    for index_name in index_names:
        for index_file in sorted(repo_root.rglob(index_name)):
            mod_dir = index_file.parent
            rel_dir = mod_dir.relative_to(repo_root)
            rel_str = str(rel_dir).replace("\\", "/")

            if any(part in _EXCLUDED_DIRS for part in rel_dir.parts):
                continue

            if rel_str in seen_paths:
                continue
            seen_paths.add(rel_str)

            mod_name = rel_dir.name if rel_dir.name != "." else rel_str
            evidence = (str(rel_dir / index_name),)
            modules.append((mod_name, rel_str, evidence))

    return modules


def _resolve_python_import_target(
    module_name: str,
    is_relative: bool,
    source_file_path: str,
    known_modules: dict[str, str],
) -> str | None:
    """Resolve a Python import to a known module path.

    Returns the module dotted name if it maps to a known module, None otherwise.
    """
    if is_relative:
        # Relative imports: resolve relative to the source file's package
        source_parts = source_file_path.replace("\\", "/").split("/")
        # Strip filename and "src" prefix if present
        pkg_parts = source_parts[:-1]  # Remove filename
        if pkg_parts and pkg_parts[0] == "src":
            pkg_parts = pkg_parts[1:]

        if module_name == ".":
            # from . import X — current package
            candidate = ".".join(pkg_parts)
        elif module_name.startswith("."):
            # Count leading dots
            dots = len(module_name) - len(module_name.lstrip("."))
            rest = module_name.lstrip(".")
            # Go up 'dots' levels
            base_parts = pkg_parts[: max(0, len(pkg_parts) - dots + 1)]
            if rest:
                base_parts.append(rest)
            candidate = ".".join(base_parts)
        else:
            # Relative import with a dotted name (e.g., from ..models import X -> "models")
            # Go up one level from current package and append the module
            base_parts = pkg_parts[:-1] if pkg_parts else []
            candidate = ".".join([*base_parts, module_name]) if base_parts else module_name
    else:
        candidate = module_name

    # Check if the candidate (or a prefix of it) is a known module
    # Try the full name first, then progressively shorter prefixes
    parts = candidate.split(".")
    for i in range(len(parts), 0, -1):
        prefix = ".".join(parts[:i])
        if prefix in known_modules:
            return prefix

    return None


def _resolve_js_import_target(
    source: str,
    source_file_path: str,
    repo_root: Path,
    known_modules: dict[str, str],
) -> str | None:
    """Resolve a JS/TS import to a known module path.

    Returns the module name if it maps to a known module, None otherwise.
    External packages (no leading . or /) are skipped.
    """
    # Skip external packages
    if not source.startswith(".") and not source.startswith("/"):
        return None

    # Resolve relative path anchored to repo root
    source_dir = repo_root / Path(source_file_path).parent
    resolved = (source_dir / source).resolve()

    try:
        rel = resolved.relative_to(repo_root.resolve())
    except ValueError:
        return None

    rel_str = str(rel).replace("\\", "/")

    # Check if this path falls within a known module (longest prefix match)
    best_match: str | None = None
    best_length = 0
    for mod_name, mod_path in known_modules.items():
        if rel_str.startswith(mod_path) and len(mod_path) > best_length:
            best_match = mod_name
            best_length = len(mod_path)

    return best_match


def _map_test_to_source(
    test_path: str,
    known_modules: dict[str, str],
) -> str | None:
    """Map a test file path to the source module it tests, by naming convention.

    Patterns:
    - tests/unit/test_foo.py -> module containing foo.py
    - tests/test_foo.py -> module containing foo.py
    - src/pkg/foo_test.py -> module containing foo.py
    - __tests__/foo.test.ts -> module containing foo.ts
    """
    parts = test_path.replace("\\", "/").split("/")
    filename = parts[-1]

    # Python: test_foo.py -> foo
    py_match = re.match(r"^test_(.+)\.py$", filename)
    if py_match:
        target_name = py_match.group(1)
        # Look for a module that contains a file named {target_name}.py
        for mod_name, mod_path in known_modules.items():
            if any(
                part == target_name or part == f"{target_name}.py" for part in mod_path.split("/")
            ):
                return mod_name
        # Try matching by the module name containing the target
        for mod_name in known_modules:
            if target_name in mod_name.split("."):
                return mod_name
        return None

    # Python: foo_test.py -> foo
    py_colocated = re.match(r"^(.+)_test\.py$", filename)
    if py_colocated:
        target_name = py_colocated.group(1)
        for mod_name in known_modules:
            if target_name in mod_name.split("."):
                return mod_name
        return None

    # JS/TS: foo.test.ts, foo.spec.ts -> foo
    js_match = re.match(r"^(.+)\.(test|spec)\.[jt]sx?$", filename)
    if js_match:
        target_name = js_match.group(1)
        for mod_name, mod_path in known_modules.items():
            if target_name in mod_path.split("/") or target_name == mod_name:
                return mod_name
        return None

    return None


def extract_boundaries(
    *,
    repo_root: Path,
    parsed_python: list[ParsedPythonFile],
    parsed_js: list[ParsedJavaScriptFile],
    graph: SqliteRepoGraph,
    repo_id: str = "",
) -> BoundaryResult:
    """Extract module boundaries, import-based edges, and test location mappings.

    Detects:
    - Python packages (via __init__.py)
    - JS/TS modules (via index.ts/index.js)
    - Import-based dependency edges between modules
    - Test directory -> source module mappings

    Each detected boundary becomes a module-boundary claim.
    """
    claims: list[BoundaryClaimInput] = []
    edges_created = 0

    # Detect modules
    py_modules = _detect_python_modules(repo_root)
    js_modules = _detect_js_modules(repo_root)

    # Build module lookup: dotted_name -> path
    known_modules: dict[str, str] = {
        dotted_name: path for dotted_name, path, _evidence in py_modules
    }
    known_modules.update({mod_name: path for mod_name, path, _evidence in js_modules})

    # Register all modules in the graph
    for mod_name in known_modules:
        graph.register_module(mod_name)

    # Create boundary claims for Python modules
    for dotted_name, path, evidence in py_modules:
        # __init__.py = clear boundary = inferred-high
        claims.append(
            BoundaryClaimInput(
                content=f"Module '{dotted_name}' — Python package at {path}/",
                source_authority=SourceAuthority.INFERRED_HIGH,
                scope=path,
                confidence=0.95,
                evidence_files=evidence,
            )
        )

    # Create boundary claims for JS/TS modules
    for mod_name, path, evidence in js_modules:
        claims.append(
            BoundaryClaimInput(
                content=f"Module '{mod_name}' — JS/TS module at {path}/",
                source_authority=SourceAuthority.INFERRED_HIGH,
                scope=path,
                confidence=0.9,
                evidence_files=evidence,
            )
        )

    # Build import-based dependency edges from Python parsed files
    for pf in parsed_python:
        source_module = _find_module_for_file(pf.path, known_modules)
        if source_module is None:
            continue

        for imp in pf.imports:
            target_module = _resolve_python_import_target(
                imp.module, imp.is_relative, pf.path, known_modules
            )
            if target_module is not None and target_module != source_module:
                graph.add_edge(source_module, target_module, "imports", repo_id)
                edges_created += 1

    # Build import-based dependency edges from JS/TS parsed files
    for jf in parsed_js:
        source_module = _find_module_for_file(jf.path, known_modules)
        if source_module is None:
            continue

        for imp in jf.imports:
            target_module = _resolve_js_import_target(
                imp.source, jf.path, repo_root, known_modules
            )
            if target_module is not None and target_module != source_module:
                graph.add_edge(source_module, target_module, "imports", repo_id)
                edges_created += 1

    # Build containment edges (parent package contains child)
    for dotted_name in list(known_modules.keys()):
        parts = dotted_name.split(".")
        if len(parts) > 1:
            parent = ".".join(parts[:-1])
            if parent in known_modules:
                graph.add_edge(parent, dotted_name, "contains", repo_id)
                edges_created += 1

    # Build test location mappings
    test_files: list[str] = [
        pf.path for pf in parsed_python if any(f.is_test for f in pf.functions)
    ]
    test_files.extend(jf.path for jf in parsed_js if jf.has_test_patterns)

    for test_path in test_files:
        target_module = _map_test_to_source(test_path, known_modules)
        if target_module is not None:
            # Use the test file's directory as the source of the test edge
            test_dir = str(Path(test_path).parent).replace("\\", "/")
            graph.add_edge(target_module, test_dir, "tests", repo_id)
            edges_created += 1

    logger.info(
        "Boundary extraction complete",
        python_modules=len(py_modules),
        js_modules=len(js_modules),
        edges_created=edges_created,
    )

    return BoundaryResult(
        claims=tuple(claims),
        modules_detected=len(known_modules),
        edges_created=edges_created,
    )


def _find_module_for_file(file_path: str, known_modules: dict[str, str]) -> str | None:
    """Find the module that owns a given file path (longest prefix match)."""
    normalized = file_path.replace("\\", "/")
    best_match: str | None = None
    best_length = 0
    for mod_name, mod_path in known_modules.items():
        if normalized.startswith(mod_path) and len(mod_path) > best_length:
            best_match = mod_name
            best_length = len(mod_path)
    return best_match
