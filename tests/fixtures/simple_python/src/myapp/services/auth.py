"""Authentication service."""

from __future__ import annotations

from myapp.core import validate_email
from myapp.models.user import get_user


def authenticate(name: str, email: str) -> bool:
    """Authenticate a user."""
    if not validate_email(email):
        return False
    user = get_user(name)
    return user.email == email
