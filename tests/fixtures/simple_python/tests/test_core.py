"""Tests for core module."""

from __future__ import annotations

from myapp.core import (
    calculate_score,
    create_user,
    validate_email,
)


def test_create_user() -> None:
    """Test user creation."""
    user = create_user("Alice", "alice@example.com")
    assert user.name == "Alice"


def test_validate_email_valid() -> None:
    """Test valid email validation."""
    assert validate_email("user@example.com")


def test_validate_email_invalid() -> None:
    """Test invalid email validation."""
    assert not validate_email("invalid")


def test_calculate_score_empty() -> None:
    """Test score calculation with empty list."""
    assert calculate_score([]) == 0.0


def test_calculate_score_values() -> None:
    """Test score calculation with values."""
    assert calculate_score([10, 20, 30]) == 20.0
