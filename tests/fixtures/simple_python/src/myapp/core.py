"""Core business logic module."""

from __future__ import annotations

from dataclasses import dataclass


MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30
API_VERSION = "2.0"


@dataclass(frozen=True)
class UserProfile:
    """A user profile in the system."""

    name: str
    email: str
    active: bool = True


@dataclass(frozen=True)
class TaskResult:
    """Result of a task execution."""

    success: bool
    message: str
    data: dict | None = None


def create_user(name: str, email: str) -> UserProfile:
    """Create a new user profile."""
    return UserProfile(name=name, email=email)


def validate_email(email: str) -> bool:
    """Validate an email address format."""
    return "@" in email and "." in email


def format_name(first: str, last: str) -> str:
    """Format a full name from first and last."""
    return f"{first} {last}"


def calculate_score(values: list[int]) -> float:
    """Calculate the average score from a list of values."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def process_data(raw: str) -> list[str]:
    """Process raw data into a list of cleaned strings."""
    return [item.strip() for item in raw.split(",") if item.strip()]


def normalize_key(key: str) -> str:
    """Normalize a key to lowercase with underscores."""
    return key.lower().replace("-", "_").replace(" ", "_")


def merge_configs(base: dict, override: dict) -> dict:
    """Merge two config dicts with override taking precedence."""
    result = dict(base)
    result.update(override)
    return result


def parse_version(version_str: str) -> tuple[int, ...]:
    """Parse a version string into a tuple of ints."""
    return tuple(int(p) for p in version_str.split("."))


def check_health(endpoint: str) -> bool:
    """Check if an endpoint is healthy."""
    return bool(endpoint)


def generate_id(prefix: str, index: int) -> str:
    """Generate a unique identifier."""
    return f"{prefix}-{index:06d}"


def truncate_text(text: str, max_length: int) -> str:
    """Truncate text to a maximum length."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def filter_active(items: list[dict]) -> list[dict]:
    """Filter a list to only active items."""
    return [item for item in items if item.get("active", False)]


def count_words(text: str) -> int:
    """Count the number of words in text."""
    return len(text.split())


def build_url(host: str, path: str) -> str:
    """Build a URL from host and path components."""
    return f"https://{host}/{path.lstrip('/')}"


def extract_domain(url: str) -> str:
    """Extract the domain from a URL."""
    return url.split("//")[-1].split("/")[0]
