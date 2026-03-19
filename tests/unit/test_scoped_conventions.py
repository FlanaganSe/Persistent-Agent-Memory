"""Unit tests for path-scoped convention refinement."""

from __future__ import annotations

from rkp.core.types import ClaimType, SourceAuthority
from rkp.indexer.extractors.conventions import (
    GlobalConventionSummary,
    extract_scoped_conventions,
)
from rkp.indexer.parsers.python import ParsedClass, ParsedFunction, ParsedPythonFile

# --- Helpers ---


def _make_func(name: str) -> ParsedFunction:
    return ParsedFunction(
        name=name,
        line_start=1,
        line_end=2,
        has_return_type=True,
        param_count=1,
        annotated_param_count=1,
        has_docstring=True,
        decorators=(),
        is_test=name.startswith("test_"),
    )


def _make_class(name: str) -> ParsedClass:
    return ParsedClass(
        name=name,
        line_start=1,
        line_end=2,
        bases=(),
        has_docstring=True,
    )


def _make_file(
    path: str,
    functions: tuple[ParsedFunction, ...] = (),
    classes: tuple[ParsedClass, ...] = (),
) -> ParsedPythonFile:
    return ParsedPythonFile(
        path=path,
        functions=functions,
        classes=classes,
        imports=(),
        constants=(),
        has_errors=False,
    )


def _snake_names(n: int) -> list[str]:
    """Generate n snake_case function names."""
    return [f"do_thing_{i}" for i in range(n)]


def _camel_names(n: int) -> list[str]:
    """Generate n camelCase function names."""
    return [f"doThing{i}" for i in range(n)]


def _pascal_names(n: int) -> list[str]:
    """Generate n PascalCase class names."""
    return [f"MyWidget{i}" for i in range(n)]


def _camel_class_names(n: int) -> list[str]:
    """Generate n camelCase class names."""
    return [f"myWidget{i}" for i in range(n)]


# Global summary where the repo uses snake_case functions and PascalCase classes.
_GLOBAL_SNAKE_PASCAL = GlobalConventionSummary(
    func_naming="snake_case",
    class_naming="PascalCase",
)


# --- Tests ---


class TestScopedClaimForDeviation:
    def test_scoped_claim_for_deviation(self) -> None:
        """Global is snake_case; one module uses camelCase with >=20 ids at >=95%."""
        camel_funcs = tuple(_make_func(n) for n in _camel_names(20))
        files = [_make_file("lib/js_compat/helpers.py", functions=camel_funcs)]

        claims = extract_scoped_conventions(
            files,
            module_paths=["lib/js_compat"],
            global_summary=_GLOBAL_SNAKE_PASCAL,
        )

        assert len(claims) == 1
        assert "camelCase" in claims[0].content
        assert "function names" in claims[0].content
        assert claims[0].claim_type == ClaimType.SCOPED_RULE


class TestNoScopedClaimForSameConvention:
    def test_no_scoped_claim_for_same_convention(self) -> None:
        """Module uses same convention as global -> no scoped rule."""
        snake_funcs = tuple(_make_func(n) for n in _snake_names(25))
        files = [_make_file("src/core/utils.py", functions=snake_funcs)]

        claims = extract_scoped_conventions(
            files,
            module_paths=["src/core"],
            global_summary=_GLOBAL_SNAKE_PASCAL,
        )

        func_claims = [c for c in claims if "function names" in c.content]
        assert func_claims == []


class TestTooFewIdentifiers:
    def test_too_few_identifiers(self) -> None:
        """Module with <20 identifiers -> no scoped convention."""
        camel_funcs = tuple(_make_func(n) for n in _camel_names(15))
        files = [_make_file("lib/tiny/mod.py", functions=camel_funcs)]

        claims = extract_scoped_conventions(
            files,
            module_paths=["lib/tiny"],
            global_summary=_GLOBAL_SNAKE_PASCAL,
        )

        assert claims == []


class TestLowConsistencyNoClaim:
    def test_low_consistency_no_claim(self) -> None:
        """Module with <80% consistency -> no claim."""
        # 10 camelCase + 11 snake_case = ~48% camelCase -> below 80%
        mixed_funcs = tuple(_make_func(n) for n in _camel_names(10) + _snake_names(11))
        files = [_make_file("lib/messy/mod.py", functions=mixed_funcs)]

        claims = extract_scoped_conventions(
            files,
            module_paths=["lib/messy"],
            global_summary=_GLOBAL_SNAKE_PASCAL,
        )

        assert claims == []


class TestScopedClaimScopeMatchesModule:
    def test_scoped_claim_scope_matches_module(self) -> None:
        """Scoped rule has scope = module_path."""
        camel_funcs = tuple(_make_func(n) for n in _camel_names(25))
        files = [_make_file("vendor/legacy/api.py", functions=camel_funcs)]

        claims = extract_scoped_conventions(
            files,
            module_paths=["vendor/legacy"],
            global_summary=_GLOBAL_SNAKE_PASCAL,
        )

        assert len(claims) == 1
        assert claims[0].scope == "vendor/legacy"


class TestInferredHighVsLow:
    def test_high_consistency_is_inferred_high(self) -> None:
        """>=95% consistency -> inferred-high."""
        # 20 camelCase, 0 other -> 100%
        camel_funcs = tuple(_make_func(n) for n in _camel_names(20))
        files = [_make_file("lib/pure_camel/mod.py", functions=camel_funcs)]

        claims = extract_scoped_conventions(
            files,
            module_paths=["lib/pure_camel"],
            global_summary=_GLOBAL_SNAKE_PASCAL,
        )

        assert len(claims) == 1
        assert claims[0].source_authority == SourceAuthority.INFERRED_HIGH

    def test_moderate_consistency_is_inferred_low(self) -> None:
        """80-94% consistency -> inferred-low."""
        # 17 camelCase + 3 snake_case = 85% camelCase (20 total)
        mixed_funcs = tuple(_make_func(n) for n in _camel_names(17) + _snake_names(3))
        files = [_make_file("lib/mostly_camel/mod.py", functions=mixed_funcs)]

        claims = extract_scoped_conventions(
            files,
            module_paths=["lib/mostly_camel"],
            global_summary=_GLOBAL_SNAKE_PASCAL,
        )

        assert len(claims) == 1
        assert claims[0].source_authority == SourceAuthority.INFERRED_LOW
        assert claims[0].confidence < 0.95


class TestClassNamingDeviation:
    def test_class_naming_deviation(self) -> None:
        """Global is PascalCase; module uses camelCase -> scoped claim."""
        camel_classes = tuple(_make_class(n) for n in _camel_class_names(20))
        files = [_make_file("lib/oddball/models.py", classes=camel_classes)]

        claims = extract_scoped_conventions(
            files,
            module_paths=["lib/oddball"],
            global_summary=_GLOBAL_SNAKE_PASCAL,
        )

        assert len(claims) == 1
        assert "camelCase" in claims[0].content
        assert "class names" in claims[0].content
        assert claims[0].claim_type == ClaimType.SCOPED_RULE
