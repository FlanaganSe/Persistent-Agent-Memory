"""Convention extractor: naming, test placement, imports, type annotations, docstrings."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

import structlog

from rkp.core.types import ClaimType, Sensitivity, SourceAuthority
from rkp.indexer.parsers.javascript import ParsedJavaScriptFile
from rkp.indexer.parsers.python import ParsedPythonFile

logger = structlog.get_logger()

# --- Naming convention classifiers ---

_SNAKE_CASE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")
_SCREAMING_SNAKE = re.compile(r"^[A-Z][A-Z0-9]*(_[A-Z0-9]+)*$")
_CAMEL_CASE = re.compile(r"^[a-z][a-zA-Z0-9]*$")
_PASCAL_CASE = re.compile(r"^[A-Z][a-zA-Z0-9]*$")

# Single-char names like 'x', 'i', '_' are too short to classify
_MIN_NAME_LENGTH = 2

# Minimum sample size per category to assert a convention
MIN_SAMPLE_SIZE = 20

# Confidence thresholds
STRONG_THRESHOLD = 0.95
WEAK_THRESHOLD = 0.80

# Tools that own formatting conventions — if detected, skip those conventions
_FORMATTER_TOOLS = frozenset({"ruff", "black", "prettier", "isort", "autopep8", "yapf"})


@dataclass(frozen=True)
class ConventionClaimInput:
    """Structured input for building a convention claim."""

    content: str
    claim_type: ClaimType
    source_authority: SourceAuthority
    scope: str
    applicability: tuple[str, ...]
    confidence: float
    sensitivity: Sensitivity
    evidence_files: tuple[str, ...]
    review_state_hint: str  # "unreviewed" or "needs-declaration"


@dataclass(frozen=True)
class NamingStats:
    """Statistics for naming convention detection in one category."""

    category: str
    total: int
    counts: dict[str, int]
    dominant_style: str | None
    consistency: float


def classify_name(name: str) -> str | None:
    """Classify an identifier's naming convention.

    Returns one of: snake_case, SCREAMING_SNAKE, camelCase, PascalCase, or None.
    """
    if len(name) < _MIN_NAME_LENGTH:
        return None
    # Leading underscore: strip for classification but still count
    stripped = name.lstrip("_")
    if len(stripped) < _MIN_NAME_LENGTH:
        return None
    if _SNAKE_CASE.match(stripped):
        return "snake_case"
    if _SCREAMING_SNAKE.match(stripped):
        return "SCREAMING_SNAKE"
    if _CAMEL_CASE.match(stripped):
        return "camelCase"
    if _PASCAL_CASE.match(stripped):
        return "PascalCase"
    return None


def _compute_naming_stats(names: list[str], category: str) -> NamingStats:
    """Compute naming convention statistics for a list of identifiers."""
    counts: Counter[str] = Counter()
    for name in names:
        style = classify_name(name)
        if style is not None:
            counts[style] += 1

    total = sum(counts.values())
    if total == 0:
        return NamingStats(
            category=category, total=0, counts=dict(counts), dominant_style=None, consistency=0.0
        )

    dominant_style, dominant_count = counts.most_common(1)[0]
    consistency = dominant_count / total

    return NamingStats(
        category=category,
        total=total,
        counts=dict(counts),
        dominant_style=dominant_style,
        consistency=consistency,
    )


def _detect_test_placement(
    parsed_files: list[ParsedPythonFile],
) -> tuple[str | None, float, list[str]]:
    """Detect the dominant test file placement pattern.

    Returns (pattern_description, confidence, evidence_files).
    """
    test_files: list[str] = []
    for pf in parsed_files:
        has_tests = any(f.is_test for f in pf.functions)
        if has_tests:
            test_files.append(pf.path)

    if not test_files:
        return None, 0.0, []

    in_tests_dir = 0
    in_test_dir = 0
    colocated = 0

    for tf in test_files:
        parts = tf.replace("\\", "/").split("/")
        if "tests" in parts:
            in_tests_dir += 1
        elif "test" in parts:
            in_test_dir += 1
        else:
            colocated += 1

    total = len(test_files)
    patterns = {
        "tests/ directory": in_tests_dir,
        "test/ directory": in_test_dir,
        "co-located test files": colocated,
    }

    dominant_pattern = max(patterns, key=lambda k: patterns[k])
    dominant_count = patterns[dominant_pattern]
    confidence = dominant_count / total if total > 0 else 0.0

    return dominant_pattern, confidence, test_files


def _detect_import_style(
    parsed_files: list[ParsedPythonFile],
) -> tuple[str | None, float, list[str]]:
    """Detect dominant import style (relative vs absolute).

    Returns (style_description, confidence, evidence_files).
    """
    absolute_count = 0
    relative_count = 0
    evidence: list[str] = []

    for pf in parsed_files:
        if not pf.imports:
            continue
        for imp in pf.imports:
            if imp.is_relative:
                relative_count += 1
            else:
                absolute_count += 1
        evidence.append(pf.path)

    total = absolute_count + relative_count
    if total < MIN_SAMPLE_SIZE:
        return None, 0.0, []

    if absolute_count >= relative_count:
        style = "absolute imports"
        confidence = absolute_count / total
    else:
        style = "relative imports"
        confidence = relative_count / total

    return style, confidence, evidence


def _detect_type_annotations(
    parsed_files: list[ParsedPythonFile],
) -> tuple[float, float, int, int, int, int, list[str]]:
    """Detect type annotation usage across all files.

    Returns (return_type_ratio, param_annotation_ratio,
             funcs_with_return, funcs_total,
             annotated_params, total_params, evidence_files).
    """
    funcs_with_return = 0
    funcs_total = 0
    annotated_params = 0
    total_params = 0
    evidence: list[str] = []

    for pf in parsed_files:
        if not pf.functions:
            continue
        evidence.append(pf.path)
        for func in pf.functions:
            funcs_total += 1
            if func.has_return_type:
                funcs_with_return += 1
            total_params += func.param_count
            annotated_params += func.annotated_param_count

    return_ratio = funcs_with_return / funcs_total if funcs_total > 0 else 0.0
    param_ratio = annotated_params / total_params if total_params > 0 else 0.0

    return (
        return_ratio,
        param_ratio,
        funcs_with_return,
        funcs_total,
        annotated_params,
        total_params,
        evidence,
    )


def _detect_docstrings(
    parsed_files: list[ParsedPythonFile],
) -> tuple[float, float, list[str]]:
    """Detect docstring presence across functions and classes.

    Returns (func_docstring_ratio, class_docstring_ratio, evidence_files).
    """
    funcs_with = 0
    funcs_total = 0
    classes_with = 0
    classes_total = 0
    evidence: list[str] = []

    for pf in parsed_files:
        if pf.functions or pf.classes:
            evidence.append(pf.path)
        for func in pf.functions:
            funcs_total += 1
            if func.has_docstring:
                funcs_with += 1
        for cls in pf.classes:
            classes_total += 1
            if cls.has_docstring:
                classes_with += 1

    func_ratio = funcs_with / funcs_total if funcs_total > 0 else 0.0
    class_ratio = classes_with / classes_total if classes_total > 0 else 0.0

    return func_ratio, class_ratio, evidence


def _authority_for_confidence(consistency: float) -> SourceAuthority:
    """Map consistency to source authority."""
    if consistency >= STRONG_THRESHOLD:
        return SourceAuthority.INFERRED_HIGH
    return SourceAuthority.INFERRED_LOW


def _review_hint_for_confidence(consistency: float) -> str:
    """Map consistency to review state hint."""
    if consistency >= STRONG_THRESHOLD:
        return "unreviewed"
    return "needs-declaration"


def extract_conventions(
    parsed_files: list[ParsedPythonFile],
    *,
    tools_detected: frozenset[str] = frozenset(),
    scope: str = "**",
) -> list[ConventionClaimInput]:
    """Extract convention claims from parsed Python files.

    Analyzes naming conventions, test placement, import style,
    type annotation usage, and docstring presence.

    If ruff/black/prettier detected in tools, skip formatting conventions.
    """
    claims: list[ConventionClaimInput] = []
    has_formatter = bool(tools_detected & _FORMATTER_TOOLS)

    # --- Naming conventions ---

    func_names: list[str] = []
    class_names: list[str] = []
    func_evidence: list[str] = []

    for pf in parsed_files:
        has_funcs = False
        for func in pf.functions:
            func_names.append(func.name)
            has_funcs = True
        class_names.extend(cls.name for cls in pf.classes)
        if has_funcs:
            func_evidence.append(pf.path)

    # Exclude test function names from naming convention analysis (they always start with test_)
    non_test_func_names = [n for n in func_names if not n.startswith("test_")]

    naming_categories = [
        ("function names", non_test_func_names, ("all",)),
        ("class names", class_names, ("all",)),
    ]

    for category_label, names, applicability in naming_categories:
        stats = _compute_naming_stats(names, category_label)
        if stats.total < MIN_SAMPLE_SIZE:
            continue
        if stats.consistency < WEAK_THRESHOLD:
            continue
        if stats.dominant_style is None:
            continue

        # If a formatter owns this, skip
        if (
            has_formatter
            and category_label == "function names"
            and stats.dominant_style == "snake_case"
        ):
            continue

        authority = _authority_for_confidence(stats.consistency)
        review_hint = _review_hint_for_confidence(stats.consistency)
        claim_type = (
            ClaimType.ALWAYS_ON_RULE
            if authority == SourceAuthority.INFERRED_HIGH
            else ClaimType.SCOPED_RULE
        )

        claims.append(
            ConventionClaimInput(
                content=f"Use {stats.dominant_style} for {category_label} "
                f"({stats.consistency:.0%} consistency across {stats.total} identifiers)",
                claim_type=claim_type,
                source_authority=authority,
                scope=scope,
                applicability=applicability,
                confidence=round(stats.consistency, 4),
                sensitivity=Sensitivity.PUBLIC,
                evidence_files=tuple(func_evidence[:10]),  # Sample, not exhaustive
                review_state_hint=review_hint,
            )
        )

    # --- Test placement ---
    test_pattern, test_confidence, test_evidence = _detect_test_placement(parsed_files)
    if test_pattern is not None and test_confidence >= WEAK_THRESHOLD:
        authority = _authority_for_confidence(test_confidence)
        review_hint = _review_hint_for_confidence(test_confidence)
        claim_type = (
            ClaimType.ALWAYS_ON_RULE
            if authority == SourceAuthority.INFERRED_HIGH
            else ClaimType.SCOPED_RULE
        )

        claims.append(
            ConventionClaimInput(
                content=f"Tests are placed in {test_pattern} "
                f"({test_confidence:.0%} of test files)",
                claim_type=claim_type,
                source_authority=authority,
                scope=scope,
                applicability=("testing",),
                confidence=round(test_confidence, 4),
                sensitivity=Sensitivity.PUBLIC,
                evidence_files=tuple(test_evidence[:10]),
                review_state_hint=review_hint,
            )
        )

    # --- Import style ---
    import_style, import_confidence, import_evidence = _detect_import_style(parsed_files)
    if import_style is not None and import_confidence >= WEAK_THRESHOLD and not has_formatter:
        authority = _authority_for_confidence(import_confidence)
        review_hint = _review_hint_for_confidence(import_confidence)
        claim_type = (
            ClaimType.ALWAYS_ON_RULE
            if authority == SourceAuthority.INFERRED_HIGH
            else ClaimType.SCOPED_RULE
        )

        claims.append(
            ConventionClaimInput(
                content=f"Prefer {import_style} ({import_confidence:.0%} consistency)",
                claim_type=claim_type,
                source_authority=authority,
                scope=scope,
                applicability=("all",),
                confidence=round(import_confidence, 4),
                sensitivity=Sensitivity.PUBLIC,
                evidence_files=tuple(import_evidence[:10]),
                review_state_hint=review_hint,
            )
        )

    # --- Type annotations ---
    (
        return_ratio,
        param_ratio,
        _funcs_with_return,
        funcs_total,
        _annotated_params,
        total_params,
        annotation_evidence,
    ) = _detect_type_annotations(parsed_files)

    if funcs_total >= MIN_SAMPLE_SIZE and return_ratio >= WEAK_THRESHOLD:
        authority = _authority_for_confidence(return_ratio)
        review_hint = _review_hint_for_confidence(return_ratio)
        claim_type = (
            ClaimType.ALWAYS_ON_RULE
            if authority == SourceAuthority.INFERRED_HIGH
            else ClaimType.SCOPED_RULE
        )

        claims.append(
            ConventionClaimInput(
                content=f"Use return type annotations on functions "
                f"({return_ratio:.0%} of {funcs_total} functions annotated)",
                claim_type=claim_type,
                source_authority=authority,
                scope=scope,
                applicability=("all",),
                confidence=round(return_ratio, 4),
                sensitivity=Sensitivity.PUBLIC,
                evidence_files=tuple(annotation_evidence[:10]),
                review_state_hint=review_hint,
            )
        )

    if total_params >= MIN_SAMPLE_SIZE and param_ratio >= WEAK_THRESHOLD:
        authority = _authority_for_confidence(param_ratio)
        review_hint = _review_hint_for_confidence(param_ratio)
        claim_type = (
            ClaimType.ALWAYS_ON_RULE
            if authority == SourceAuthority.INFERRED_HIGH
            else ClaimType.SCOPED_RULE
        )

        claims.append(
            ConventionClaimInput(
                content=f"Use parameter type annotations "
                f"({param_ratio:.0%} of {total_params} parameters annotated)",
                claim_type=claim_type,
                source_authority=authority,
                scope=scope,
                applicability=("all",),
                confidence=round(param_ratio, 4),
                sensitivity=Sensitivity.PUBLIC,
                evidence_files=tuple(annotation_evidence[:10]),
                review_state_hint=review_hint,
            )
        )

    # --- Docstrings ---
    func_doc_ratio, _class_doc_ratio, doc_evidence = _detect_docstrings(parsed_files)

    # Only assert docstring conventions for functions if enough functions exist
    if funcs_total >= MIN_SAMPLE_SIZE and func_doc_ratio >= WEAK_THRESHOLD:
        authority = _authority_for_confidence(func_doc_ratio)
        review_hint = _review_hint_for_confidence(func_doc_ratio)
        claim_type = (
            ClaimType.ALWAYS_ON_RULE
            if authority == SourceAuthority.INFERRED_HIGH
            else ClaimType.SCOPED_RULE
        )

        claims.append(
            ConventionClaimInput(
                content=f"Include docstrings on functions "
                f"({func_doc_ratio:.0%} of functions have docstrings)",
                claim_type=claim_type,
                source_authority=authority,
                scope=scope,
                applicability=("all",),
                confidence=round(func_doc_ratio, 4),
                sensitivity=Sensitivity.PUBLIC,
                evidence_files=tuple(doc_evidence[:10]),
                review_state_hint=review_hint,
            )
        )

    return claims


# --- Path-scoped convention refinement ---


@dataclass(frozen=True)
class GlobalConventionSummary:
    """Summary of global conventions for deviation comparison."""

    func_naming: str | None  # e.g., "snake_case"
    class_naming: str | None  # e.g., "PascalCase"


def summarize_global_conventions(claims: list[ConventionClaimInput]) -> GlobalConventionSummary:
    """Extract the dominant naming conventions from global claims."""
    func_naming: str | None = None
    class_naming: str | None = None
    for claim in claims:
        if "function names" in claim.content:
            for style in ("snake_case", "camelCase", "PascalCase", "SCREAMING_SNAKE"):
                if style in claim.content:
                    func_naming = style
                    break
        elif "class names" in claim.content:
            for style in ("snake_case", "camelCase", "PascalCase", "SCREAMING_SNAKE"):
                if style in claim.content:
                    class_naming = style
                    break
    return GlobalConventionSummary(func_naming=func_naming, class_naming=class_naming)


def extract_scoped_conventions(
    parsed_files: list[ParsedPythonFile],
    module_paths: list[str],
    global_summary: GlobalConventionSummary,
    *,
    tools_detected: frozenset[str] = frozenset(),
) -> list[ConventionClaimInput]:
    """Extract per-module convention claims that DEVIATE from global conventions.

    Only creates scoped claims when a module's dominant convention differs
    from the global convention and meets the minimum sample size threshold.
    """
    scoped_claims: list[ConventionClaimInput] = []

    for module_path in sorted(module_paths):
        # Collect files belonging to this module
        module_files = [
            pf
            for pf in parsed_files
            if pf.path.replace("\\", "/").startswith(module_path.rstrip("/") + "/")
            or pf.path.replace("\\", "/") == module_path
        ]
        if not module_files:
            continue

        # Collect function names for this module
        func_names: list[str] = []
        func_evidence: list[str] = []
        class_names: list[str] = []

        for pf in module_files:
            has_funcs = False
            for func in pf.functions:
                if not func.name.startswith("test_"):
                    func_names.append(func.name)
                    has_funcs = True
            class_names.extend(cls.name for cls in pf.classes)
            if has_funcs:
                func_evidence.append(pf.path)

        # Check function naming deviation
        func_stats = _compute_naming_stats(func_names, "function names")
        if (
            func_stats.total >= MIN_SAMPLE_SIZE
            and func_stats.consistency >= WEAK_THRESHOLD
            and func_stats.dominant_style is not None
            and func_stats.dominant_style != global_summary.func_naming
        ):
            has_formatter = bool(tools_detected & _FORMATTER_TOOLS)
            if not (has_formatter and func_stats.dominant_style == "snake_case"):
                authority = _authority_for_confidence(func_stats.consistency)
                scoped_claims.append(
                    ConventionClaimInput(
                        content=f"Use {func_stats.dominant_style} for function names "
                        f"({func_stats.consistency:.0%} consistency across "
                        f"{func_stats.total} identifiers)",
                        claim_type=ClaimType.SCOPED_RULE,
                        source_authority=authority,
                        scope=module_path,
                        applicability=("all",),
                        confidence=round(func_stats.consistency, 4),
                        sensitivity=Sensitivity.PUBLIC,
                        evidence_files=tuple(func_evidence[:10]),
                        review_state_hint=_review_hint_for_confidence(func_stats.consistency),
                    )
                )

        # Check class naming deviation
        class_stats = _compute_naming_stats(class_names, "class names")
        if (
            class_stats.total >= MIN_SAMPLE_SIZE
            and class_stats.consistency >= WEAK_THRESHOLD
            and class_stats.dominant_style is not None
            and class_stats.dominant_style != global_summary.class_naming
        ):
            authority = _authority_for_confidence(class_stats.consistency)
            scoped_claims.append(
                ConventionClaimInput(
                    content=f"Use {class_stats.dominant_style} for class names "
                    f"({class_stats.consistency:.0%} consistency across "
                    f"{class_stats.total} identifiers)",
                    claim_type=ClaimType.SCOPED_RULE,
                    source_authority=authority,
                    scope=module_path,
                    applicability=("all",),
                    confidence=round(class_stats.consistency, 4),
                    sensitivity=Sensitivity.PUBLIC,
                    evidence_files=tuple(pf.path for pf in module_files[:10]),
                    review_state_hint=_review_hint_for_confidence(class_stats.consistency),
                )
            )

    return scoped_claims


# --- Test framework detection for JS/TS ---

_JS_TEST_FRAMEWORKS: dict[str, str] = {
    "jest": "Jest",
    "vitest": "Vitest",
    "mocha": "Mocha",
    "@jest/globals": "Jest",
    "@testing-library": "Testing Library",
}


def _detect_js_test_framework(
    parsed_files: list[ParsedJavaScriptFile],
) -> tuple[str | None, float, list[str]]:
    """Detect JS/TS test framework from import patterns."""
    framework_counts: Counter[str] = Counter()
    evidence: list[str] = []

    for pf in parsed_files:
        if not pf.has_test_patterns:
            continue
        evidence.append(pf.path)
        for imp in pf.imports:
            for pattern, name in _JS_TEST_FRAMEWORKS.items():
                if pattern in imp.source:
                    framework_counts[name] += 1

    if not framework_counts:
        # No explicit imports, but test patterns detected — likely Jest (default)
        if evidence:
            return "Jest (inferred from test patterns)", 0.8, evidence
        return None, 0.0, []

    dominant, count = framework_counts.most_common(1)[0]
    total = sum(framework_counts.values())
    confidence = count / total if total > 0 else 0.0

    return dominant, confidence, evidence


def _detect_js_test_placement(
    parsed_files: list[ParsedJavaScriptFile],
) -> tuple[str | None, float, list[str]]:
    """Detect JS/TS test file placement pattern."""
    test_files = [pf.path for pf in parsed_files if pf.has_test_patterns]

    if not test_files:
        return None, 0.0, []

    in_tests_dir = 0
    in_test_dir = 0
    colocated = 0

    for tf in test_files:
        parts = tf.replace("\\", "/").split("/")
        if "__tests__" in parts:
            in_tests_dir += 1
        elif any(p in parts for p in ("tests", "test")):
            in_test_dir += 1
        elif ".test." in tf or ".spec." in tf:
            colocated += 1
        else:
            colocated += 1

    total = len(test_files)
    patterns = {
        "__tests__/ directory": in_tests_dir,
        "tests/ or test/ directory": in_test_dir,
        "co-located (*.test.* / *.spec.*)": colocated,
    }

    dominant_pattern = max(patterns, key=lambda k: patterns[k])
    dominant_count = patterns[dominant_pattern]
    confidence = dominant_count / total if total > 0 else 0.0

    return dominant_pattern, confidence, test_files


def extract_js_conventions(
    parsed_files: list[ParsedJavaScriptFile],
    *,
    tools_detected: frozenset[str] = frozenset(),
    scope: str = "**",
) -> list[ConventionClaimInput]:
    """Extract convention claims from parsed JS/TS files.

    Analyzes naming conventions (camelCase functions, PascalCase classes),
    test framework detection, test file placement, and TypeScript usage.
    """
    claims: list[ConventionClaimInput] = []
    has_formatter = bool(tools_detected & _FORMATTER_TOOLS)

    # --- Naming conventions ---
    func_names: list[str] = []
    class_names: list[str] = []
    func_evidence: list[str] = []

    for pf in parsed_files:
        if pf.functions:
            func_evidence.append(pf.path)
        func_names.extend(func.name for func in pf.functions)
        class_names.extend(cls.name for cls in pf.classes)

    naming_categories: list[tuple[str, list[str], tuple[str, ...]]] = [
        ("function names", func_names, ("all",)),
        ("class names", class_names, ("all",)),
    ]

    for category_label, names, applicability in naming_categories:
        stats = _compute_naming_stats(names, category_label)
        if stats.total < MIN_SAMPLE_SIZE:
            continue
        if stats.consistency < WEAK_THRESHOLD:
            continue
        if stats.dominant_style is None:
            continue

        if has_formatter and category_label == "function names":
            continue

        authority = _authority_for_confidence(stats.consistency)
        review_hint = _review_hint_for_confidence(stats.consistency)
        claim_type = (
            ClaimType.ALWAYS_ON_RULE
            if authority == SourceAuthority.INFERRED_HIGH
            else ClaimType.SCOPED_RULE
        )

        claims.append(
            ConventionClaimInput(
                content=f"Use {stats.dominant_style} for {category_label} "
                f"({stats.consistency:.0%} consistency across {stats.total} identifiers)",
                claim_type=claim_type,
                source_authority=authority,
                scope=scope,
                applicability=applicability,
                confidence=round(stats.consistency, 4),
                sensitivity=Sensitivity.PUBLIC,
                evidence_files=tuple(func_evidence[:10]),
                review_state_hint=review_hint,
            )
        )

    # --- Test framework ---
    framework, fw_confidence, fw_evidence = _detect_js_test_framework(parsed_files)
    if framework is not None and fw_confidence >= WEAK_THRESHOLD:
        authority = _authority_for_confidence(fw_confidence)
        review_hint = _review_hint_for_confidence(fw_confidence)
        claims.append(
            ConventionClaimInput(
                content=f"Test framework: {framework}",
                claim_type=ClaimType.ALWAYS_ON_RULE
                if authority == SourceAuthority.INFERRED_HIGH
                else ClaimType.SCOPED_RULE,
                source_authority=authority,
                scope=scope,
                applicability=("testing",),
                confidence=round(fw_confidence, 4),
                sensitivity=Sensitivity.PUBLIC,
                evidence_files=tuple(fw_evidence[:10]),
                review_state_hint=review_hint,
            )
        )

    # --- Test placement ---
    test_pattern, test_confidence, test_evidence = _detect_js_test_placement(parsed_files)
    if test_pattern is not None and test_confidence >= WEAK_THRESHOLD:
        authority = _authority_for_confidence(test_confidence)
        review_hint = _review_hint_for_confidence(test_confidence)
        claims.append(
            ConventionClaimInput(
                content=f"Tests are placed in {test_pattern} "
                f"({test_confidence:.0%} of test files)",
                claim_type=ClaimType.ALWAYS_ON_RULE
                if authority == SourceAuthority.INFERRED_HIGH
                else ClaimType.SCOPED_RULE,
                source_authority=authority,
                scope=scope,
                applicability=("testing",),
                confidence=round(test_confidence, 4),
                sensitivity=Sensitivity.PUBLIC,
                evidence_files=tuple(test_evidence[:10]),
                review_state_hint=review_hint,
            )
        )

    # --- TypeScript usage ---
    ts_count = sum(1 for pf in parsed_files if pf.language == "typescript")
    js_count = sum(1 for pf in parsed_files if pf.language == "javascript")
    total_js_ts = ts_count + js_count
    if total_js_ts >= MIN_SAMPLE_SIZE:
        ts_ratio = ts_count / total_js_ts
        if ts_ratio >= WEAK_THRESHOLD:
            authority = _authority_for_confidence(ts_ratio)
            review_hint = _review_hint_for_confidence(ts_ratio)
            claims.append(
                ConventionClaimInput(
                    content=f"TypeScript is the primary language "
                    f"({ts_ratio:.0%} of {total_js_ts} JS/TS files)",
                    claim_type=ClaimType.ALWAYS_ON_RULE
                    if authority == SourceAuthority.INFERRED_HIGH
                    else ClaimType.SCOPED_RULE,
                    source_authority=authority,
                    scope=scope,
                    applicability=("all",),
                    confidence=round(ts_ratio, 4),
                    sensitivity=Sensitivity.PUBLIC,
                    evidence_files=tuple(pf.path for pf in parsed_files[:10]),
                    review_state_hint=review_hint,
                )
            )

    return claims
