"""User model."""

from __future__ import annotations

from myapp.core import UserProfile


def get_user(name: str) -> UserProfile:
    """Get a user by name."""
    return UserProfile(name=name, email=f"{name}@example.com")
