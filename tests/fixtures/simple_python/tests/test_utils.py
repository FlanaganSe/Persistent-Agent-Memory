"""Tests for utility functions."""

from __future__ import annotations

from myapp.utils import (
    chunk_list,
    clamp,
    deduplicate,
    flatten_list,
    safe_divide,
    to_snake_case,
)


def test_to_snake_case() -> None:
    """Test snake case conversion."""
    assert to_snake_case("HelloWorld") == "hello_world"


def test_flatten_list() -> None:
    """Test list flattening."""
    assert flatten_list([[1, 2], [3, 4]]) == [1, 2, 3, 4]


def test_chunk_list() -> None:
    """Test list chunking."""
    assert chunk_list([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]


def test_deduplicate() -> None:
    """Test deduplication."""
    assert deduplicate(["a", "b", "a", "c"]) == ["a", "b", "c"]


def test_safe_divide() -> None:
    """Test safe division."""
    assert safe_divide(10.0, 2.0) == 5.0


def test_safe_divide_by_zero() -> None:
    """Test safe division by zero."""
    assert safe_divide(10.0, 0.0) == 0.0


def test_clamp() -> None:
    """Test value clamping."""
    assert clamp(5, 0, 10) == 5
    assert clamp(-1, 0, 10) == 0
    assert clamp(15, 0, 10) == 10
