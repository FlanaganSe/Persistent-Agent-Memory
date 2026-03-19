"""Unit tests for the Python tree-sitter parser."""

from __future__ import annotations

from pathlib import Path

from rkp.indexer.parsers.python import parse_python_file


class TestParsePythonFile:
    def test_extract_functions(self) -> None:
        source = b"""
def foo(x: int, y: str) -> bool:
    \"\"\"A docstring.\"\"\"
    return True

def bar():
    pass
"""
        result = parse_python_file(Path("test.py"), source=source)
        assert len(result.functions) == 2

        foo = next(f for f in result.functions if f.name == "foo")
        assert foo.has_return_type
        assert foo.param_count == 2
        assert foo.annotated_param_count == 2
        assert foo.has_docstring

        bar = next(f for f in result.functions if f.name == "bar")
        assert not bar.has_return_type
        assert bar.param_count == 0
        assert not bar.has_docstring

    def test_extract_classes(self) -> None:
        source = b"""
class MyClass:
    \"\"\"A class docstring.\"\"\"
    pass

class ChildClass(MyClass):
    pass
"""
        result = parse_python_file(Path("test.py"), source=source)
        assert len(result.classes) == 2

        my_class = next(c for c in result.classes if c.name == "MyClass")
        assert my_class.has_docstring
        assert my_class.bases == ()

        child = next(c for c in result.classes if c.name == "ChildClass")
        assert not child.has_docstring
        assert "MyClass" in child.bases

    def test_extract_imports(self) -> None:
        source = b"""
import os
import sys
from pathlib import Path
from . import local_module
from ..sibling import helper
"""
        result = parse_python_file(Path("test.py"), source=source)
        assert len(result.imports) >= 4

        modules = [i.module for i in result.imports]
        assert "os" in modules
        assert "sys" in modules
        assert "pathlib" in modules

        # Relative imports detected
        relative = [i for i in result.imports if i.is_relative]
        assert len(relative) == 2

    def test_extract_test_functions(self) -> None:
        source = b"""
def test_something():
    assert True

def test_another_thing():
    assert 1 == 1

def helper():
    pass
"""
        result = parse_python_file(Path("test.py"), source=source)
        tests = [f for f in result.functions if f.is_test]
        assert len(tests) == 2
        assert all(f.name.startswith("test_") for f in tests)

    def test_extract_constants(self) -> None:
        source = b"""
MAX_SIZE = 100
DEFAULT_NAME = "hello"
_PRIVATE = True
regular_var = 42
"""
        result = parse_python_file(Path("test.py"), source=source)
        assert "MAX_SIZE" in result.constants
        assert "DEFAULT_NAME" in result.constants

    def test_empty_file(self) -> None:
        result = parse_python_file(Path("empty.py"), source=b"")
        assert result.functions == ()
        assert result.classes == ()
        assert result.imports == ()
        assert result.constants == ()
        assert not result.has_errors

    def test_syntax_error_graceful(self) -> None:
        # Use clearly broken syntax that tree-sitter cannot recover from
        source = b"def ( { [ broken syntax @#$ \n  class \n"
        result = parse_python_file(Path("broken.py"), source=source)
        assert result.has_errors
        # Should still produce partial results, not crash

    def test_no_functions(self) -> None:
        source = b"# Just a comment\nx = 1\n"
        result = parse_python_file(Path("no_funcs.py"), source=source)
        assert result.functions == ()

    def test_method_self_excluded_from_params(self) -> None:
        source = b"""
class Foo:
    def method(self, x: int) -> None:
        pass
"""
        result = parse_python_file(Path("test.py"), source=source)
        method = next(f for f in result.functions if f.name == "method")
        assert method.param_count == 1  # self excluded
        assert method.annotated_param_count == 1

    def test_multi_method_class_params_correct(self) -> None:
        """Multiple methods in a class get correct param counts (not index-correlated)."""
        source = b"""
class MyService:
    def method_a(self, x: int, y: str) -> bool:
        pass

    def method_b(self) -> None:
        pass

    def method_c(self, name: str) -> str:
        pass

def top_level(a: int, b: int, c: int) -> int:
    return a + b + c
"""
        result = parse_python_file(Path("test.py"), source=source)
        funcs = {f.name: f for f in result.functions}

        assert funcs["method_a"].param_count == 2
        assert funcs["method_a"].annotated_param_count == 2
        assert funcs["method_a"].has_return_type

        assert funcs["method_b"].param_count == 0
        assert funcs["method_b"].has_return_type

        assert funcs["method_c"].param_count == 1
        assert funcs["method_c"].annotated_param_count == 1

        assert funcs["top_level"].param_count == 3
        assert funcs["top_level"].annotated_param_count == 3
        assert funcs["top_level"].has_return_type
