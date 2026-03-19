# Claim Model

Claims are the canonical data model. Every piece of repo knowledge — conventions, commands, prerequisites, guardrails, boundaries — is a claim with provenance, confidence, and review state.

## Claim Schema

| Field | Type | Description |
|---|---|---|
| `id` | string | Content-addressable ID: `claim-` + `SHA-256(claim_type:scope:content)[:16]` |
| `content` | string | The claim text (e.g., "Use frozen dataclasses for domain models") |
| `claim_type` | ClaimType | Category of knowledge (see table below) |
| `source_authority` | SourceAuthority | How the claim was discovered (see hierarchy) |
| `scope` | string | File/directory glob the claim applies to. `**` = repo-wide |
| `applicability` | tuple[str] | Task tags: `build`, `test`, `lint`, `format`, etc. |
| `sensitivity` | Sensitivity | `public`, `team-only`, or `local-only` |
| `review_state` | ReviewState | Human governance state |
| `confidence` | float | 0.0–1.0 extraction confidence |
| `evidence` | tuple[str] | File paths where the claim was extracted from |
| `provenance` | Provenance | Extraction metadata (index_version, repo_head, branch, timestamp) |
| `risk_class` | RiskClass? | For commands: `safe-readonly` through `destructive` |
| `projection_targets` | tuple[str] | Which hosts this claim should project to |
| `last_validated` | datetime? | When evidence was last checked |
| `revalidation_trigger` | string? | Why the claim went stale |
| `stale` | bool | Whether evidence has changed since last validation |

## Claim Types

| Type | Description | Typical projection |
|---|---|---|
| `always-on-rule` | Repo-wide convention or rule | Always-on section of instruction files |
| `scoped-rule` | Convention scoped to a path or module | Path-scoped rules (Claude rules/, Cursor rules/) |
| `skill-playbook` | Detailed procedure or workflow | Skills (SKILL.md files, .claude/skills/) |
| `environment-prerequisite` | Runtime, tool, or service dependency | Prerequisites section, setup-steps |
| `validated-command` | Build/test/lint command with evidence | Commands section with risk classification |
| `permission-restriction` | Security guardrail or dangerous operation | Permissions (Claude settings.json, Copilot tool allowlist) |
| `module-boundary` | Import-based dependency relationship | Module info responses |
| `conflict` | Disagreement between declared and inferred knowledge | Conflict warnings |

## Source Authority Hierarchy

Lower precedence number = higher authority. When claims conflict, the higher-authority claim wins.

| Authority | Precedence | Description |
|---|---|---|
| `human-override` | 10 | Explicit human decision via `rkp review` |
| `declared-reviewed` | 20 | Imported claim that a human has reviewed and approved |
| `executable-config` | 30 | From pyproject.toml, package.json, Makefile, Dockerfile |
| `ci-observed` | 30 | From GitHub Actions workflows |
| `declared-imported-unreviewed` | 35 | Imported from existing instruction files, not yet reviewed |
| `checked-in-docs` | 40 | From README, docs/, or other checked-in documentation |
| `inferred-high` | 50 | Inferred from code with high confidence (e.g., consistent patterns) |
| `inferred-low` | 60 | Inferred from code with low confidence |

Key design decision: imported claims (`declared-imported-unreviewed` at 35) do **not** outrank executable config (30). A `pytest` command found in `pyproject.toml` outranks an unreviewed claim from an imported `AGENTS.md`. After human review, imported claims are promoted to `declared-reviewed` (20).

## Review State Machine

```
                  ┌──────────────────────────────────────┐
                  │              unreviewed               │
                  └──────┬──────┬──────┬──────┬──────────┘
                         │      │      │      │
                    approve   edit  suppress  tombstone
                         │      │      │      │
                         v      v      v      v
                    approved  edited  suppressed  tombstoned

                  ┌──────────────────────────────────────┐
                  │          needs-declaration            │
                  └──────────────┬───────────────────────┘
                                 │
                             respond
                                 │
                                 v
                             approved
```

- **unreviewed**: default state after extraction
- **approved**: human confirmed the claim is correct
- **edited**: human modified the claim content (preserves original ID)
- **suppressed**: human says "don't project this" — hidden from projection but kept in store
- **tombstoned**: hard-deleted from projection and marked for cleanup
- **needs-declaration**: claim requires a human declaration (e.g., confirming a destructive command is intentional)

## Sensitivity Levels

| Level | Where it appears | Where it never appears |
|---|---|---|
| `public` | Everywhere: instruction files, MCP responses, overrides | — |
| `team-only` | `.rkp/overrides/` (version-controlled) | MCP responses without authentication |
| `local-only` | `.rkp/local/` database only | Instruction files, MCP responses, overrides |

Sensitivity filtering is enforced at a single point (`projection/sensitivity.py`), called just before every output boundary. Claims with detected secrets are automatically set to `local-only`.

## Evidence Levels

For validated commands, evidence levels indicate how thoroughly a command has been verified:

| Level | Description |
|---|---|
| `discovered` | Found in a config file (pyproject.toml, package.json, Makefile) |
| `prerequisites-extracted` | Runtime/tool prerequisites identified for the command |
| `ci-evidenced` | Command found in CI workflow with pass/fail context |
| `environment-profiled` | Full environment profile (runtime, tools, services, env vars) built |
| `sandbox-verified` | Command executed in sandbox and verified (Phase 2) |

## Risk Classification

Commands are classified by risk to help agents make safe decisions:

| Risk Class | Description | Example |
|---|---|---|
| `safe-readonly` | No side effects, no mutation | `ruff check`, `pyright` |
| `safe-mutating` | Mutates local files predictably | `ruff format`, `npm install` |
| `test-execution` | Runs tests, may have side effects | `pytest`, `npm test` |
| `build` | Build artifacts, may take significant time | `uv build`, `npm run build` |
| `destructive` | Potentially destructive operations | `rm -rf`, `git clean -fdx` |

## Claim ID Generation

IDs are computed as `claim-` + `SHA-256(claim_type + ":" + scope + ":" + content)` truncated to 16 hex characters.

Properties:
- **Deterministic**: same input always produces the same ID (enables deduplication)
- **Immutable**: edits to a claim change content but preserve the original ID
- **Stable across re-extraction**: re-extracting the same repo produces the same claim IDs
- **Collision-resistant**: 16 hex chars = 64 bits, sufficient for single-repo workloads

## Freshness Model

Claims go stale when their supporting evidence changes. Three triggers:

1. **Evidence changed**: a source file's hash differs from the hash at extraction time
2. **Branch changed**: the current branch differs from the branch at index time
3. **Time expired**: claim hasn't been validated within the staleness window (default: 90 days)

When a claim is stale, its effective confidence is reduced multiplicatively: `confidence * (1 - reduction_factor)`. Default reduction: 20%. The `stale` flag and `revalidation_trigger` field let agents and humans know why.

The freshness checker falls back to `git diff` between indexed HEAD and current HEAD when the `claim_evidence` table has no records (which is the common case for extracted claims in Phase 1).

## Applicability Vocabulary

Claims carry applicability tags that scope them to specific task types. The controlled core vocabulary:

`build`, `test`, `lint`, `format`, `docs`, `review`, `refactor`, `debug`, `security`, `ci`, `release`, `onboarding`

Custom tags are allowed beyond the core set. The special tag `all` means the claim applies to every task context. Agents can filter claims by task context (e.g., "give me only `test`-applicable conventions").
