"""Utility functions for the application."""

from __future__ import annotations

import os


BATCH_SIZE = 100
CACHE_TTL = 3600


class ConfigManager:
    """Manages application configuration."""

    def __init__(self, path: str) -> None:
        """Initialize with config file path."""
        self.path = path
        self.data: dict = {}

    def load(self) -> dict:
        """Load configuration from file."""
        return self.data

    def get_value(self, key: str) -> str | None:
        """Get a configuration value by key."""
        return self.data.get(key)


class EventBus:
    """Simple event bus for decoupled communication."""

    def __init__(self) -> None:
        """Initialize the event bus."""
        self.handlers: dict[str, list] = {}

    def subscribe(self, event: str, handler: object) -> None:
        """Subscribe a handler to an event."""
        self.handlers.setdefault(event, []).append(handler)

    def publish(self, event: str) -> None:
        """Publish an event to all subscribers."""
        for handler in self.handlers.get(event, []):
            handler()


def get_env_var(name: str, default: str = "") -> str:
    """Get an environment variable with a default."""
    return os.environ.get(name, default)


def to_snake_case(text: str) -> str:
    """Convert a string to snake_case."""
    result = []
    for char in text:
        if char.isupper():
            result.append("_")
            result.append(char.lower())
        else:
            result.append(char)
    return "".join(result).lstrip("_")


def flatten_list(nested: list[list]) -> list:
    """Flatten a nested list into a single list."""
    return [item for sublist in nested for item in sublist]


def chunk_list(items: list, size: int) -> list[list]:
    """Split a list into chunks of a given size."""
    return [items[i : i + size] for i in range(0, len(items), size)]


def deduplicate(items: list[str]) -> list[str]:
    """Remove duplicates while preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def safe_divide(numerator: float, denominator: float) -> float:
    """Safely divide two numbers, returning 0.0 on division by zero."""
    if denominator == 0.0:
        return 0.0
    return numerator / denominator


def clamp(value: int, minimum: int, maximum: int) -> int:
    """Clamp a value between minimum and maximum."""
    return max(minimum, min(value, maximum))


def is_valid_identifier(name: str) -> bool:
    """Check if a string is a valid Python identifier."""
    return name.isidentifier()
