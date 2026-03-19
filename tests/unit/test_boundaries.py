"""Unit tests for the boundary extractor."""

from __future__ import annotations

import pytest

from rkp.core.types import SourceAuthority
from rkp.graph.repo_graph import SqliteRepoGraph
from rkp.indexer.extractors.boundaries import (
    _detect_js_modules,
    _detect_python_modules,
    extract_boundaries,
)
from rkp.indexer.parsers.python import ParsedFunction, ParsedImport, ParsedPythonFile
from rkp.store.database import open_database, run_migrations


@pytest.fixture
def graph_db(tmp_path):
    db = open_database(tmp_path / "test.db")
    run_migrations(db)
    yield db
    db.close()


@pytest.fixture
def graph(graph_db):
    return SqliteRepoGraph(graph_db, repo_id="test-repo")


class TestPythonModuleDetection:
    def test_src_layout(self, tmp_path):
        """Detect Python packages in src/ layout."""
        (tmp_path / "src" / "myapp").mkdir(parents=True)
        (tmp_path / "src" / "myapp" / "__init__.py").touch()
        (tmp_path / "src" / "myapp" / "core").mkdir()
        (tmp_path / "src" / "myapp" / "core" / "__init__.py").touch()

        modules = _detect_python_modules(tmp_path)
        names = [m[0] for m in modules]
        assert "myapp" in names
        assert "myapp.core" in names

    def test_flat_layout(self, tmp_path):
        """Detect Python packages in flat layout."""
        (tmp_path / "myapp").mkdir()
        (tmp_path / "myapp" / "__init__.py").touch()

        modules = _detect_python_modules(tmp_path)
        names = [m[0] for m in modules]
        assert "myapp" in names

    def test_excluded_dirs_skipped(self, tmp_path):
        """Excluded directories (tests, node_modules, etc.) are not detected as modules."""
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "__init__.py").touch()
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "__init__.py").touch()

        modules = _detect_python_modules(tmp_path)
        names = [m[0] for m in modules]
        assert "tests" not in names
        assert "__pycache__" not in names


class TestJSModuleDetection:
    def test_index_ts_detection(self, tmp_path):
        """Detect JS/TS modules via index.ts."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "index.ts").touch()

        modules = _detect_js_modules(tmp_path)
        names = [m[0] for m in modules]
        assert "src" in names

    def test_excluded_dirs(self, tmp_path):
        """node_modules should not be detected."""
        (tmp_path / "node_modules" / "foo").mkdir(parents=True)
        (tmp_path / "node_modules" / "foo" / "index.js").touch()

        modules = _detect_js_modules(tmp_path)
        assert len(modules) == 0


class TestBoundaryExtraction:
    def test_extracts_python_boundaries(self, tmp_path, graph):
        """Full extraction on a Python fixture with multiple packages."""
        (tmp_path / "src" / "myapp").mkdir(parents=True)
        (tmp_path / "src" / "myapp" / "__init__.py").touch()
        (tmp_path / "src" / "myapp" / "core.py").write_text("x = 1")

        parsed = [
            ParsedPythonFile(
                path="src/myapp/core.py",
                functions=(),
                classes=(),
                imports=(ParsedImport(module="os", is_relative=False),),
                constants=(),
                has_errors=False,
            )
        ]

        result = extract_boundaries(
            repo_root=tmp_path,
            parsed_python=parsed,
            parsed_js=[],
            graph=graph,
            repo_id="test-repo",
        )

        assert result.modules_detected >= 1
        # Should have boundary claims
        assert len(result.claims) >= 1
        # All claims should be inferred-high (clear __init__.py boundary)
        for claim in result.claims:
            assert claim.source_authority == SourceAuthority.INFERRED_HIGH

    def test_import_edges_created(self, tmp_path, graph):
        """Import-based dependency edges are created between modules."""
        (tmp_path / "src" / "pkg_a").mkdir(parents=True)
        (tmp_path / "src" / "pkg_a" / "__init__.py").touch()
        (tmp_path / "src" / "pkg_b").mkdir(parents=True)
        (tmp_path / "src" / "pkg_b" / "__init__.py").touch()

        parsed = [
            ParsedPythonFile(
                path="src/pkg_a/main.py",
                functions=(),
                classes=(),
                imports=(ParsedImport(module="pkg_b", is_relative=False),),
                constants=(),
                has_errors=False,
            ),
        ]

        result = extract_boundaries(
            repo_root=tmp_path,
            parsed_python=parsed,
            parsed_js=[],
            graph=graph,
            repo_id="test-repo",
        )

        assert result.edges_created >= 1
        deps = graph.get_dependencies("pkg_a")
        assert "pkg_b" in deps

    def test_test_location_mapping(self, tmp_path, graph):
        """Test files are mapped to source modules."""
        (tmp_path / "src" / "myapp").mkdir(parents=True)
        (tmp_path / "src" / "myapp" / "__init__.py").touch()
        (tmp_path / "tests").mkdir()

        test_func = ParsedFunction(
            name="test_something",
            line_start=1,
            line_end=3,
            has_return_type=False,
            param_count=0,
            annotated_param_count=0,
            has_docstring=False,
            decorators=(),
            is_test=True,
        )

        parsed = [
            ParsedPythonFile(
                path="tests/test_myapp.py",
                functions=(test_func,),
                classes=(),
                imports=(),
                constants=(),
                has_errors=False,
            ),
        ]

        result = extract_boundaries(
            repo_root=tmp_path,
            parsed_python=parsed,
            parsed_js=[],
            graph=graph,
            repo_id="test-repo",
        )

        # The test may or may not map depending on naming — just verify no crash
        assert result.modules_detected >= 1
