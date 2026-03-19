"""Unit tests for the convention extractor."""

from __future__ import annotations

from rkp.core.types import SourceAuthority
from rkp.indexer.extractors.conventions import (
    classify_name,
    extract_conventions,
)
from rkp.indexer.parsers.python import ParsedClass, ParsedFunction, ParsedImport, ParsedPythonFile


def _make_func(
    name: str, has_return_type: bool = True, has_docstring: bool = True
) -> ParsedFunction:
    return ParsedFunction(
        name=name,
        line_start=1,
        line_end=2,
        has_return_type=has_return_type,
        param_count=1,
        annotated_param_count=1 if has_return_type else 0,
        has_docstring=has_docstring,
        decorators=(),
        is_test=name.startswith("test_"),
    )


def _make_file(
    path: str,
    functions: tuple[ParsedFunction, ...] = (),
    classes: tuple[ParsedClass, ...] = (),
    imports: tuple[ParsedImport, ...] = (),
) -> ParsedPythonFile:
    return ParsedPythonFile(
        path=path,
        functions=functions,
        classes=classes,
        imports=imports,
        constants=(),
        has_errors=False,
    )


class TestClassifyName:
    def test_snake_case(self) -> None:
        assert classify_name("my_function") == "snake_case"
        assert classify_name("get_value") == "snake_case"

    def test_screaming_snake(self) -> None:
        assert classify_name("MAX_SIZE") == "SCREAMING_SNAKE"
        assert classify_name("API_KEY") == "SCREAMING_SNAKE"

    def test_camel_case(self) -> None:
        assert classify_name("myFunction") == "camelCase"
        assert classify_name("getValue") == "camelCase"

    def test_pascal_case(self) -> None:
        assert classify_name("MyClass") == "PascalCase"
        assert classify_name("UserProfile") == "PascalCase"

    def test_short_name(self) -> None:
        assert classify_name("x") is None
        assert classify_name("_") is None

    def test_leading_underscore(self) -> None:
        assert classify_name("_private_func") == "snake_case"
        assert classify_name("__dunder") == "snake_case"


class TestExtractConventions:
    def test_strong_snake_case_convention(self) -> None:
        """25 snake_case functions → inferred-high at 1.0."""
        funcs = tuple(_make_func(f"func_{i}") for i in range(25))
        files = [_make_file("mod.py", functions=funcs)]
        claims = extract_conventions(files)

        naming_claims = [c for c in claims if "function names" in c.content]
        assert len(naming_claims) == 1
        assert naming_claims[0].source_authority == SourceAuthority.INFERRED_HIGH
        assert naming_claims[0].confidence == 1.0

    def test_weak_convention_threshold(self) -> None:
        """18 snake_case + 2 camelCase → 90%, below 95%, should be inferred-low."""
        funcs = tuple(_make_func(f"func_{i}") for i in range(18))
        funcs = (*funcs, _make_func("camelFuncA"), _make_func("camelFuncB"))
        files = [_make_file("mod.py", functions=funcs)]
        claims = extract_conventions(files)

        naming_claims = [c for c in claims if "function names" in c.content]
        assert len(naming_claims) == 1
        assert naming_claims[0].source_authority == SourceAuthority.INFERRED_LOW
        assert naming_claims[0].confidence < 0.95

    def test_minimum_sample_too_small(self) -> None:
        """Only 15 functions → no convention asserted."""
        funcs = tuple(_make_func(f"func_{i}") for i in range(15))
        files = [_make_file("mod.py", functions=funcs)]
        claims = extract_conventions(files)

        naming_claims = [c for c in claims if "function names" in c.content]
        assert len(naming_claims) == 0

    def test_formatter_suppresses_naming_convention(self) -> None:
        """If ruff is detected, do not assert snake_case for function names."""
        funcs = tuple(_make_func(f"func_{i}") for i in range(25))
        files = [_make_file("mod.py", functions=funcs)]
        claims = extract_conventions(files, tools_detected=frozenset({"ruff"}))

        naming_claims = [c for c in claims if "function names" in c.content]
        assert len(naming_claims) == 0

    def test_test_placement_detected(self) -> None:
        """Test files in tests/ directory detected."""
        test_funcs = tuple(_make_func(f"test_case_{i}") for i in range(5))
        files = [
            _make_file("tests/test_a.py", functions=test_funcs),
            _make_file("tests/test_b.py", functions=test_funcs),
        ]
        claims = extract_conventions(files)

        placement_claims = [c for c in claims if "Tests are placed" in c.content]
        assert len(placement_claims) == 1
        assert "tests/ directory" in placement_claims[0].content

    def test_type_annotation_convention(self) -> None:
        """High return type annotation usage → convention detected."""
        funcs = tuple(_make_func(f"func_{i}", has_return_type=True) for i in range(25))
        files = [_make_file("mod.py", functions=funcs)]
        claims = extract_conventions(files)

        annotation_claims = [c for c in claims if "return type annotations" in c.content]
        assert len(annotation_claims) == 1
        assert annotation_claims[0].confidence >= 0.95

    def test_no_convention_below_threshold(self) -> None:
        """Mixed naming → no convention if below 80%."""
        snake = tuple(_make_func(f"func_{i}") for i in range(10))
        camel = tuple(_make_func(f"funcCamel{i}") for i in range(10))
        funcs = snake + camel
        files = [_make_file("mod.py", functions=funcs)]
        claims = extract_conventions(files)

        # Should have no naming convention (50/50 split below 80%)
        naming_claims = [c for c in claims if "function names" in c.content]
        assert len(naming_claims) == 0

    def test_empty_files_no_crash(self) -> None:
        """Empty file list produces no claims."""
        claims = extract_conventions([])
        assert claims == []

    def test_class_naming_convention(self) -> None:
        """PascalCase classes → convention detected."""
        classes = tuple(
            ParsedClass(name=f"MyClass{i}", line_start=1, line_end=2, bases=(), has_docstring=True)
            for i in range(25)
        )
        files = [_make_file("mod.py", classes=classes)]
        claims = extract_conventions(files)

        class_claims = [c for c in claims if "class names" in c.content]
        assert len(class_claims) == 1
        assert "PascalCase" in class_claims[0].content
