"""Security utilities: safe YAML, path traversal prevention, injection detection, secret scanning."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from rkp.core.errors import InjectionDetectedError, PathTraversalError, UnsafeYamlError

# ---------------------------------------------------------------------------
# Injection detection
# ---------------------------------------------------------------------------


class Severity:
    """Injection finding severity levels."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class InjectionFinding:
    """A single injection marker match."""

    marker: str
    line_number: int
    context: str
    severity: str
    in_code_block: bool = False


# (pattern, base_severity)
_INJECTION_MARKERS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Direct instruction injection — HIGH
    (re.compile(r"\[INST\]", re.IGNORECASE), Severity.HIGH),
    (re.compile(r"\[/INST\]", re.IGNORECASE), Severity.HIGH),
    (re.compile(r"<\|im_start\|>", re.IGNORECASE), Severity.HIGH),
    (re.compile(r"<\|im_end\|>", re.IGNORECASE), Severity.HIGH),
    (re.compile(r"<<SYS>>"), Severity.HIGH),
    (re.compile(r"<</SYS>>"), Severity.HIGH),
    # Instruction override attempts — HIGH
    (re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.IGNORECASE), Severity.HIGH),
    (re.compile(r"ignore\s+(all\s+)?prior\s+instructions?", re.IGNORECASE), Severity.HIGH),
    (re.compile(r"disregard\s+(all\s+)?previous", re.IGNORECASE), Severity.HIGH),
    (re.compile(r"forget\s+(all\s+)?previous", re.IGNORECASE), Severity.HIGH),
    (re.compile(r"new\s+instructions?\s*:", re.IGNORECASE), Severity.HIGH),
    (re.compile(r"override\s+instructions?\s*:", re.IGNORECASE), Severity.HIGH),
    # Role impersonation — MEDIUM (allow leading whitespace)
    (re.compile(r"^\s*System:\s", re.MULTILINE), Severity.MEDIUM),
    (re.compile(r"^\s*Assistant:\s", re.MULTILINE), Severity.MEDIUM),
    (re.compile(r"^\s*Human:\s", re.MULTILINE), Severity.MEDIUM),
    (re.compile(r"^\s*User:\s", re.MULTILINE), Severity.MEDIUM),
    # Structured injection — MEDIUM
    (re.compile(r"<tool_call>", re.IGNORECASE), Severity.MEDIUM),
    (re.compile(r"</tool_call>", re.IGNORECASE), Severity.MEDIUM),
    (re.compile(r"<function_call>", re.IGNORECASE), Severity.MEDIUM),
    (re.compile(r"<\|tool\|>", re.IGNORECASE), Severity.MEDIUM),
    # Suspicious but could be legitimate — LOW
    (re.compile(r"you\s+are\s+now\s+a", re.IGNORECASE), Severity.LOW),
    (re.compile(r"act\s+as\s+if", re.IGNORECASE), Severity.LOW),
    (re.compile(r"pretend\s+you\s+are", re.IGNORECASE), Severity.LOW),
)

# Code-block detection for false-positive reduction.
_CODE_FENCE_OPEN = re.compile(r"^```", re.MULTILINE)
_CODE_FENCE_CLOSE = re.compile(r"^```\s*$", re.MULTILINE)

_SEVERITY_ORDER = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}


def _downgrade_severity(severity: str) -> str:
    """Reduce severity by one level (for code-block context)."""
    if severity == Severity.HIGH:
        return Severity.MEDIUM
    if severity == Severity.MEDIUM:
        return Severity.LOW
    return Severity.LOW


def _compute_code_block_ranges(content: str) -> list[tuple[int, int]]:
    """Return (start_line, end_line) ranges that are inside fenced code blocks."""
    ranges: list[tuple[int, int]] = []
    lines = content.split("\n")
    in_block = False
    block_start = 0
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            if not in_block:
                in_block = True
                block_start = i
            else:
                in_block = False
                ranges.append((block_start, i))
    # Unclosed code block: treat rest as code block.
    if in_block:
        ranges.append((block_start, len(lines)))
    return ranges


def _line_in_code_block(line_num: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= line_num <= end for start, end in ranges)


def scan_for_injection(content: str) -> list[InjectionFinding]:
    """Scan content for prompt injection markers.

    Returns a list of findings, each with: marker matched, line number,
    context snippet, severity (high/medium/low).

    Content inside fenced code blocks gets severity reduced by one level.
    """
    if not content:
        return []

    findings: list[InjectionFinding] = []
    code_block_ranges = _compute_code_block_ranges(content)
    lines = content.split("\n")

    for pattern, base_severity in _INJECTION_MARKERS:
        for match in pattern.finditer(content):
            # Compute line number.
            line_num = content[: match.start()].count("\n") + 1
            in_code = _line_in_code_block(line_num, code_block_ranges)
            severity = _downgrade_severity(base_severity) if in_code else base_severity

            # Context snippet: the line containing the match.
            line_idx = line_num - 1
            ctx = lines[line_idx] if line_idx < len(lines) else ""
            if len(ctx) > 120:
                ctx = ctx[:120] + "..."

            findings.append(
                InjectionFinding(
                    marker=match.group(0),
                    line_number=line_num,
                    context=ctx,
                    severity=severity,
                    in_code_block=in_code,
                )
            )

    # Sort by severity (HIGH first), then line number.
    findings.sort(key=lambda f: (_SEVERITY_ORDER.get(f.severity, 9), f.line_number))
    return findings


def max_injection_severity(findings: list[InjectionFinding]) -> str | None:
    """Return the highest severity from a list of findings, or None if empty."""
    if not findings:
        return None
    for sev in (Severity.HIGH, Severity.MEDIUM, Severity.LOW):
        if any(f.severity == sev for f in findings):
            return sev
    return None


# ---------------------------------------------------------------------------
# Secret detection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SecretFinding:
    """A potential secret detected in content.

    WARNING: ``matched_value`` contains the raw secret for use by ``redact_secrets()``
    only. Never log, serialize, or return this field in API responses.
    """

    pattern_type: str
    line_number: int
    redacted_context: str
    matched_value: str  # raw value — see warning above; used only by redact_secrets()


# (regex, description) — the first capture group (if any) is the secret value.
_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Provider-specific (check these first — more precise).
    (re.compile(r"(?:AKIA|ASIA)[A-Z0-9]{16}"), "AWS access key"),
    (re.compile(r"ghp_[A-Za-z0-9]{36}"), "GitHub personal access token"),
    (re.compile(r"gho_[A-Za-z0-9]{36}"), "GitHub OAuth token"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{82}"), "GitHub fine-grained PAT"),
    (re.compile(r"sk-ant-[A-Za-z0-9\-]{90,}"), "Anthropic API key"),
    (re.compile(r"sk-[A-Za-z0-9]{48}"), "OpenAI API key"),
    (re.compile(r"xoxb-[0-9]{10,13}-[0-9]{10,13}-[A-Za-z0-9]{24}"), "Slack bot token"),
    (re.compile(r"xoxp-[0-9]{10,13}-[0-9]{10,13}-[A-Za-z0-9]{24}"), "Slack user token"),
    # Connection strings.
    (
        re.compile(r"(?:postgres|mysql|mongodb)://[^\s]+:[^\s]+@[^\s]+"),
        "Database connection string",
    ),
    (re.compile(r"redis://[^\s]*:[^\s]+@[^\s]+"), "Redis connection string"),
    # Private keys.
    (re.compile(r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----"), "Private key"),
    (re.compile(r"-----BEGIN OPENSSH PRIVATE KEY-----"), "SSH private key"),
    # Generic key/token/secret in assignment context.
    (
        re.compile(r"(?:api[_-]?key|apikey)\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{20,})", re.IGNORECASE),
        "API key",
    ),
    (
        re.compile(
            r"(?:secret[_-]?key|secret)\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{20,})", re.IGNORECASE
        ),
        "Secret key",
    ),
    (
        re.compile(
            r"(?:access[_-]?token|token)\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{20,})", re.IGNORECASE
        ),
        "Access token",
    ),
    (
        re.compile(r"(?:auth[_-]?token)\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{20,})", re.IGNORECASE),
        "Auth token",
    ),
)

# Pattern for high-entropy strings in assignment context.
_ASSIGNMENT_PATTERN = re.compile(
    r"""(?:password|passwd|pwd|secret|token|key|api_key|apikey|auth)\s*[:=]\s*['"]([^'"]{20,})['"]""",
    re.IGNORECASE,
)

# Patterns to exclude from entropy checks (structured, not secrets).
_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)
_GIT_HASH_PATTERN = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


def _shannon_entropy(s: str) -> float:
    """Compute Shannon entropy of a string."""
    if not s:
        return 0.0
    counts = Counter(s)
    length = len(s)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def _is_structured_non_secret(value: str) -> bool:
    """Return True if the string looks like a UUID, git hash, or other structured data."""
    if _UUID_PATTERN.match(value):
        return True
    return bool(_GIT_HASH_PATTERN.match(value))


def scan_for_secrets(content: str) -> list[SecretFinding]:
    """Scan content for potential secrets.

    Returns list of findings with: pattern type, line number,
    redacted context (secret value masked), matched value.
    """
    if not content:
        return []

    findings: list[SecretFinding] = []
    lines = content.split("\n")
    seen_positions: set[tuple[int, int]] = set()

    # Pattern-based detection.
    for pattern, description in _SECRET_PATTERNS:
        for match in pattern.finditer(content):
            pos_key = (match.start(), match.end())
            if pos_key in seen_positions:
                continue
            seen_positions.add(pos_key)

            line_num = content[: match.start()].count("\n") + 1
            # Use the first capture group if it exists, else the full match.
            secret_value = (
                match.group(1) if match.lastindex and match.lastindex >= 1 else match.group(0)
            )
            line_idx = line_num - 1
            line_text = lines[line_idx] if line_idx < len(lines) else ""

            # Redact the secret in the context.
            redacted = _redact_in_line(line_text, secret_value)

            findings.append(
                SecretFinding(
                    pattern_type=description,
                    line_number=line_num,
                    redacted_context=redacted,
                    matched_value=secret_value,
                )
            )

    # Entropy-based detection for assignment contexts.
    for match in _ASSIGNMENT_PATTERN.finditer(content):
        pos_key = (match.start(), match.end())
        if pos_key in seen_positions:
            continue

        value = match.group(1)
        if _is_structured_non_secret(value):
            continue
        if len(value) < 20:
            continue

        entropy = _shannon_entropy(value)
        if entropy > 4.5:
            seen_positions.add(pos_key)
            line_num = content[: match.start()].count("\n") + 1
            line_idx = line_num - 1
            line_text = lines[line_idx] if line_idx < len(lines) else ""
            redacted = _redact_in_line(line_text, value)

            findings.append(
                SecretFinding(
                    pattern_type="High-entropy secret",
                    line_number=line_num,
                    redacted_context=redacted,
                    matched_value=value,
                )
            )

    findings.sort(key=lambda f: f.line_number)
    return findings


def redact_secrets(content: str, findings: list[SecretFinding]) -> str:
    """Replace secret values in content with REDACTED markers."""
    result = content
    # Process longest matches first to avoid partial replacements.
    for finding in sorted(findings, key=lambda f: -len(f.matched_value)):
        if finding.matched_value in result:
            prefix = finding.matched_value[:4] if len(finding.matched_value) > 8 else ""
            result = result.replace(finding.matched_value, f"{prefix}...REDACTED")
    return result


def _redact_in_line(line: str, secret: str) -> str:
    """Redact a secret value within a line of text."""
    if secret not in line:
        return line
    prefix = secret[:4] if len(secret) > 8 else ""
    return line.replace(secret, f"{prefix}...REDACTED")


# ---------------------------------------------------------------------------
# Legacy API (preserved for backward compatibility with M1 tests)
# ---------------------------------------------------------------------------

# Simplified injection markers used by the legacy detect_injection_markers().
_LEGACY_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\[INST\]", re.IGNORECASE),
    re.compile(r"\bSystem:\s", re.IGNORECASE),
    re.compile(r"\brole:\s*(system|assistant|user)\b", re.IGNORECASE),
    re.compile(r"ignore\s+previous\s+instructions?", re.IGNORECASE),
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
    re.compile(r"<\|im_end\|>", re.IGNORECASE),
    re.compile(r"```\s*system\b", re.IGNORECASE),
)


def safe_yaml_load(content: object) -> Any:
    """Load YAML content safely using yaml.safe_load().

    Never uses yaml.load() which can execute arbitrary Python code.
    Accepts object to enforce string type at runtime (security boundary).
    """
    if not isinstance(content, str):
        msg = "YAML content must be a string"
        raise UnsafeYamlError(msg)
    return yaml.safe_load(content)


def validate_path(path: Path, repo_root: Path) -> Path:
    """Validate that a path is contained within the repo root.

    Resolves symlinks and verifies the resolved path starts with the
    resolved repo root. Rejects paths containing null bytes.
    """
    path_str = str(path)
    if "\x00" in path_str:
        raise PathTraversalError(path_str, str(repo_root))

    resolved_root = repo_root.resolve()
    resolved_path = (repo_root / path).resolve()

    if not resolved_path.is_relative_to(resolved_root):
        raise PathTraversalError(str(path), str(repo_root))

    return resolved_path


def detect_injection_markers(content: str) -> list[str]:
    """Scan content for prompt injection markers.

    Returns a list of matched marker descriptions. Empty list means clean.

    This is the legacy API preserved for backward compatibility.
    For new code, use scan_for_injection() which returns structured findings.
    """
    found: list[str] = []
    for pattern in _LEGACY_INJECTION_PATTERNS:
        match = pattern.search(content)
        if match:
            found.append(match.group(0))
    return found


def require_no_injection(content: str) -> None:
    """Raise InjectionDetectedError if injection markers are found."""
    markers = detect_injection_markers(content)
    if markers:
        raise InjectionDetectedError(markers)
