"""Import engine: discover, parse, and ingest existing instruction files as claims."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import structlog

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.errors import DuplicateClaimError
from rkp.core.models import Claim, Provenance
from rkp.core.security import (
    Severity,
    max_injection_severity,
    redact_secrets,
    scan_for_injection,
    scan_for_secrets,
)
from rkp.core.types import (
    ArtifactOwnership,
    ClaimType,
    ReviewState,
    Sensitivity,
    SourceAuthority,
)
from rkp.importer.models import (
    ImportResult,
    ParsedClaimInput,
    ParsedInstructionFile,
    UnparseableSection,
)
from rkp.importer.parsers.agents_md import parse_agents_md
from rkp.importer.parsers.claude_md import parse_claude_md
from rkp.importer.parsers.copilot import parse_copilot_instructions, parse_copilot_setup_steps
from rkp.importer.parsers.cursor import parse_cursor_rules
from rkp.store.artifacts import SqliteArtifactStore
from rkp.store.claims import ClaimStore

logger = structlog.get_logger()


def discover_instruction_files(repo_root: Path) -> list[tuple[str, Path]]:
    """Discover known instruction file patterns in a repository.

    Returns list of (source_type, file_path) tuples.
    """
    found: list[tuple[str, Path]] = []

    # AGENTS.md at root and nested
    agents_root = repo_root / "AGENTS.md"
    if agents_root.is_file():
        found.append(("agents-md", agents_root))
    found.extend(
        ("agents-md", p)
        for p in sorted(repo_root.rglob("AGENTS.md"))
        if p != agents_root and p.is_file()
    )

    # CLAUDE.md at root and nested
    claude_root = repo_root / "CLAUDE.md"
    if claude_root.is_file():
        found.append(("claude-md", claude_root))
    found.extend(
        ("claude-md", p)
        for p in sorted(repo_root.rglob("CLAUDE.md"))
        if p != claude_root and p.is_file()
    )

    # Copilot: .github/copilot-instructions.md
    copilot_instructions = repo_root / ".github" / "copilot-instructions.md"
    if copilot_instructions.is_file():
        found.append(("copilot-instructions", copilot_instructions))

    # Copilot: .github/instructions/**/*.instructions.md
    instructions_dir = repo_root / ".github" / "instructions"
    if instructions_dir.is_dir():
        found.extend(
            ("copilot-scoped-instructions", p)
            for p in sorted(instructions_dir.rglob("*.instructions.md"))
            if p.is_file()
        )

    # Copilot: prefer the projected workflow path, but keep legacy import compatibility.
    setup_steps_candidates = (
        repo_root / ".github" / "workflows" / "copilot-setup-steps.yml",
        repo_root / ".github" / "copilot-setup-steps.yml",
    )
    for setup_steps in setup_steps_candidates:
        if setup_steps.is_file():
            found.append(("copilot-setup-steps", setup_steps))
            break

    # Cursor: .cursor/rules or .cursorrules
    cursor_rules_dir = repo_root / ".cursor" / "rules"
    if cursor_rules_dir.is_dir():
        found.extend(
            ("cursor-rules", p) for p in sorted(cursor_rules_dir.rglob("*")) if p.is_file()
        )

    cursorrules_file = repo_root / ".cursorrules"
    if cursorrules_file.is_file():
        found.append(("cursor-rules", cursorrules_file))

    return found


def parse_instruction_file(
    source_type: str,
    file_path: Path,
    repo_root: Path,
) -> ParsedInstructionFile:
    """Parse a single instruction file by type.

    Returns a ParsedInstructionFile with extracted claims, unparseable sections,
    and warnings.
    """
    # Compute scope from path relative to repo root
    scope = _scope_from_path(file_path, repo_root)

    if source_type == "agents-md":
        return parse_agents_md(file_path, scope_prefix=scope)
    elif source_type == "claude-md":
        return parse_claude_md(file_path, scope_prefix=scope)
    elif source_type in ("copilot-instructions", "copilot-scoped-instructions"):
        return parse_copilot_instructions(file_path, scope_prefix=scope)
    elif source_type == "copilot-setup-steps":
        return parse_copilot_setup_steps(file_path)
    elif source_type == "cursor-rules":
        results = parse_cursor_rules(file_path, scope_prefix=scope)
        if results:
            return results[0]
        return ParsedInstructionFile(
            source_path=str(file_path),
            source_type="cursor-rules",
            claims=(),
            unparseable_sections=(),
            warnings=(),
        )
    else:
        return ParsedInstructionFile(
            source_path=str(file_path),
            source_type=source_type,
            claims=(),
            unparseable_sections=(),
            warnings=(f"Unknown source type: {source_type}",),
        )


def run_import(
    repo_root: Path,
    claim_store: ClaimStore,
    *,
    repo_id: str = "",
    branch: str = "main",
    source_path: Path | None = None,
    take_ownership: bool = False,
    dry_run: bool = False,
    artifact_store: SqliteArtifactStore | None = None,
) -> ImportResult:
    """Run the full import workflow.

    1. Discover instruction files (or use source_path for specific file)
    2. Parse each file
    3. Security scan (already done in parsers, verify here)
    4. Create claims (DECLARED_IMPORTED_UNREVIEWED, precedence 3.5)
    5. Deduplicate against existing claims
    6. Surface conflicts
    7. Register in managed_artifacts

    Args:
        repo_root: Repository root directory.
        claim_store: Store for persisting claims.
        repo_id: Repository identifier.
        branch: Current branch name.
        source_path: If set, import only this specific file.
        take_ownership: If True, set managed-by-rkp instead of imported-human-owned.
        dry_run: If True, parse and report but don't persist.
        artifact_store: Store for tracking managed artifacts.

    Returns:
        ImportResult with summary of the import operation.
    """
    builder = ClaimBuilder(repo_id=repo_id, branch=branch)

    # Step 1: Discover
    if source_path is not None:
        source_type = _guess_source_type(source_path)
        discovered = [(source_type, source_path)]
    else:
        discovered = discover_instruction_files(repo_root)

    if not discovered:
        return ImportResult(
            files_discovered=(),
            files_parsed=(),
            claims_created=0,
            claims_deduplicated=0,
            conflicts_found=0,
            unparseable_sections=(),
            security_warnings=(),
            warnings=("No instruction files found.",),
        )

    files_discovered = tuple(str(fp) for _, fp in discovered)

    # Step 2: Parse
    all_parsed: list[ParsedInstructionFile] = []
    for source_type, file_path in discovered:
        parsed = parse_instruction_file(source_type, file_path, repo_root)
        all_parsed.append(parsed)

    files_parsed = tuple(p.source_path for p in all_parsed if p.claims)

    # Step 3: Collect warnings and unparseable sections
    all_warnings: list[str] = []
    all_security_warnings: list[str] = []
    all_unparseable: list[UnparseableSection] = []

    for parsed in all_parsed:
        all_warnings.extend(parsed.warnings)
        all_unparseable.extend(parsed.unparseable_sections)
        # Separate security warnings
        all_security_warnings.extend(
            w for w in parsed.warnings if "Injection" in w or "secret" in w.lower()
        )

    # Step 4: Build claims
    new_claims: list[Claim] = []
    for parsed in all_parsed:
        for claim_input in parsed.claims:
            claim = _build_imported_claim(builder, claim_input, parsed.source_path)
            claim = _security_scan_imported_claim(claim, all_warnings)
            new_claims.append(claim)

    # Step 5: Deduplicate
    existing_claims = claim_store.list_claims(repo_id=repo_id)
    unique, duplicates = builder.deduplicate(new_claims, existing_claims)

    # Step 6: Persist (unless dry_run)
    if not dry_run:
        for claim in unique:
            try:
                claim_store.save(claim)
            except DuplicateClaimError:
                duplicates.append(claim)

    # Step 7: Run conflict detection on imported vs extracted
    conflicts_found = 0
    if not dry_run and unique:
        all_claims = claim_store.list_claims(repo_id=repo_id)
        conflicts_found = _detect_import_conflicts(all_claims, builder, claim_store)

    # Step 8: Register in managed_artifacts
    if not dry_run and artifact_store is not None:
        ownership = (
            ArtifactOwnership.MANAGED_BY_RKP
            if take_ownership
            else ArtifactOwnership.IMPORTED_HUMAN_OWNED
        )
        for parsed in all_parsed:
            if parsed.claims and parsed.content_hash:
                rel_path = _relative_path(parsed.source_path, repo_root)
                target_host = _host_from_source_type(parsed.source_type)
                # Protect imported-human-owned artifacts from silent overwrite
                existing_artifact = artifact_store.get_artifact(rel_path)
                if (
                    existing_artifact is not None
                    and existing_artifact.ownership_mode == ArtifactOwnership.IMPORTED_HUMAN_OWNED
                    and ownership != ArtifactOwnership.IMPORTED_HUMAN_OWNED
                ):
                    all_warnings.append(
                        f"{rel_path}: already tracked as imported-human-owned. "
                        f"Use --take-ownership to change ownership mode."
                    )
                    continue
                artifact_store.register_artifact(
                    path=rel_path,
                    artifact_type="instruction-file",
                    target_host=target_host,
                    expected_hash=parsed.content_hash,
                    ownership=ownership,
                )

    logger.info(
        "Import complete",
        files_discovered=len(files_discovered),
        files_parsed=len(files_parsed),
        claims_created=len(unique),
        claims_deduplicated=len(duplicates),
        conflicts_found=conflicts_found,
        unparseable=len(all_unparseable),
    )

    return ImportResult(
        files_discovered=files_discovered,
        files_parsed=files_parsed,
        claims_created=len(unique),
        claims_deduplicated=len(duplicates),
        conflicts_found=conflicts_found,
        unparseable_sections=tuple(all_unparseable),
        security_warnings=tuple(all_security_warnings),
        warnings=tuple(all_warnings),
    )


def _build_imported_claim(
    builder: ClaimBuilder,
    claim_input: ParsedClaimInput,
    source_path: str,
) -> Claim:
    """Build a claim from a parsed import input at DECLARED_IMPORTED_UNREVIEWED authority."""
    claim = builder.build(
        content=claim_input.content,
        claim_type=claim_input.claim_type,
        source_authority=SourceAuthority.DECLARED_IMPORTED_UNREVIEWED,
        scope=claim_input.scope,
        applicability=claim_input.applicability,
        confidence=claim_input.confidence,
        evidence=(claim_input.evidence_file or source_path,),
        provenance=Provenance(
            extraction_version="import-0.1.0",
            timestamp="",
        ),
    )
    return replace(claim, review_state=ReviewState.UNREVIEWED)


def _security_scan_imported_claim(claim: Claim, warnings: list[str]) -> Claim:
    """Scan an imported claim for injection markers and secrets."""
    injection_findings = scan_for_injection(claim.content)
    if injection_findings:
        sev = max_injection_severity(injection_findings)
        markers = [f.marker for f in injection_findings]
        warnings.append(f"Injection marker in imported claim {claim.id}: {markers}")
        if sev == Severity.HIGH:
            claim = replace(claim, review_state=ReviewState.NEEDS_DECLARATION)

    secret_findings = scan_for_secrets(claim.content)
    if secret_findings:
        types = [f.pattern_type for f in secret_findings]
        warnings.append(f"Secret redacted in imported claim {claim.id}: {types}")
        redacted = redact_secrets(claim.content, secret_findings)
        claim = replace(
            claim,
            content=redacted,
            sensitivity=Sensitivity.LOCAL_ONLY,
        )

    return claim


def _detect_import_conflicts(
    all_claims: list[Claim],
    builder: ClaimBuilder,
    claim_store: ClaimStore,
) -> int:
    """Detect conflicts between imported claims and extracted evidence.

    Looks for:
    - Imported commands not found in any config (stale instruction)
    - Imported prerequisites contradicting CI evidence
    - Imported conventions contradicting inferred conventions
    """
    from rkp.indexer.extractors.conflicts import detect_conflicts

    conflict_result = detect_conflicts(all_claims)
    conflicts_added = 0

    for conflict_input in conflict_result.conflicts:
        conflict_claim = builder.build(
            content=conflict_input.content,
            claim_type=ClaimType.CONFLICT,
            source_authority=conflict_input.source_authority,
            scope=conflict_input.scope,
            applicability=(),
            confidence=conflict_input.confidence,
            evidence=conflict_input.evidence_claim_ids,
            provenance=Provenance(extraction_version="import-0.1.0", timestamp=""),
        )
        conflict_claim = replace(conflict_claim, review_state=ReviewState.NEEDS_DECLARATION)
        try:
            claim_store.save(conflict_claim)
            conflicts_added += 1
        except DuplicateClaimError:
            pass

    return conflicts_added


def _scope_from_path(file_path: Path, repo_root: Path) -> str:
    """Compute scope prefix from file path relative to repo root.

    Root-level files get "**" scope. Nested files get their parent directory as scope.
    """
    try:
        rel = file_path.relative_to(repo_root)
    except ValueError:
        return "**"

    parent = str(rel.parent)
    if parent == ".":
        return "**"
    return f"{parent}/**"


def _relative_path(abs_path: str, repo_root: Path) -> str:
    """Convert absolute path to relative path string."""
    try:
        return str(Path(abs_path).relative_to(repo_root))
    except ValueError:
        return abs_path


def _guess_source_type(file_path: Path) -> str:
    """Guess source type from file name/path."""
    name = file_path.name
    path_str = str(file_path)

    if name == "AGENTS.md":
        return "agents-md"
    if name == "CLAUDE.md":
        return "claude-md"
    if name == "copilot-instructions.md":
        return "copilot-instructions"
    if name.endswith(".instructions.md"):
        return "copilot-scoped-instructions"
    if name == "copilot-setup-steps.yml":
        return "copilot-setup-steps"
    if ".cursor" in path_str or name == ".cursorrules":
        return "cursor-rules"
    # Default: treat as generic markdown
    return "agents-md"


def _host_from_source_type(source_type: str) -> str:
    """Map source type to target host identifier."""
    if source_type in ("agents-md",):
        return "codex"
    if source_type in ("claude-md",):
        return "claude"
    if source_type in (
        "copilot-instructions",
        "copilot-scoped-instructions",
        "copilot-setup-steps",
    ):
        return "copilot"
    if source_type in ("cursor-rules",):
        return "cursor"
    return "unknown"
