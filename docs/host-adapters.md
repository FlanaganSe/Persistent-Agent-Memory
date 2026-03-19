# Host Adapters

RKP projects canonical claims into each agent's native instruction format. Five adapters translate the shared claim store into host-specific surfaces.

## Host Capability Matrix

| Capability | AGENTS.md | CLAUDE.md | Copilot | Cursor | Windsurf |
|---|:---:|:---:|:---:|:---:|:---:|
| Always-on rules | Yes | Yes | Yes | Yes | Yes |
| Scoped rules | Yes (dir overrides) | Yes (paths frontmatter) | Yes (applyTo) | Yes (globs) | Yes (trigger) |
| Skills | Yes (.agents/skills/) | Yes (.claude/skills/) | Yes (setup-steps) | No | No |
| Environment config | No | Yes | Yes (setup-steps.yml) | No | No |
| Permissions | No | Yes (settings.json) | Yes (tool allowlist) | No | No |
| Hard budget | 32 KiB | — | — | — | 6 KiB (12 KiB workspace) |
| Soft budget | — | 200 lines | 300 lines | 500 lines | — |
| Maturity | **GA** | **GA** | **Beta** | **Alpha** | **Alpha** |

## Adapter Maturity Tiers

Maturity is earned via the quality conformance harness, not declared at implementation time.

- **GA** (AGENTS.md, CLAUDE.md): >= 95% conformance score, zero sensitivity leakage, drift detection pass
- **Beta** (Copilot): conformance pass with documented gaps
- **Alpha** (Cursor, Windsurf): export-only, conformance tests run but gaps expected

## Projection Rules

1. **Thin-by-default**: always-on files contain only high-confidence, broadly applicable rules. Detailed procedures go to skills/on-demand surfaces.
2. **Approved-only for apply**: `rkp apply` only projects claims with `review_state` in {`approved`, `edited`}. Preview shows all claims regardless.
3. **Precedence ordering**: higher-authority claims appear first in projected output.
4. **Sensitivity filtering**: `team-only` and `local-only` claims are excluded from all projected files. Single enforcement point.
5. **Budget enforcement**: content is trimmed to fit host size constraints. Overflow is routed to skills or excluded with a report.
6. **Deterministic output**: same claim state produces identical projected files.
7. **Deduplication**: Windsurf auto-reads AGENTS.md, so the Windsurf adapter deduplicates claims already in AGENTS.md projection.
8. **Generation header**: all projected files include a provenance header with generation timestamp and source version.
9. **No inference in adapters**: adapters format claims, they never infer new ones.
10. **Scope preservation**: path-scoped claims project to path-scoped surfaces where the host supports them.

## AGENTS.md (GA)

**Output files**: `AGENTS.md` at repo root, optional `.agents/skills/*.md` for detailed content, nested `AGENTS.md` files in subdirectories for scoped overrides.

**Structure**:
- Generation header with provenance
- Conventions section (always-on rules sorted by precedence)
- Validated commands section (commands with risk classification)
- Prerequisites section (environment requirements)
- Guardrails section (restrictions and dangerous operations)

**Budget**: 32 KiB hard limit. Content exceeding the budget is routed to skills files or excluded with an overflow report.

**Skills**: detailed procedures are projected to `.agents/skills/SKILL.md` files, referenced from the main `AGENTS.md`.

## CLAUDE.md (GA)

**Output files**: `CLAUDE.md` at repo root, `.claude/rules/*.md` for path-scoped rules, `.claude/skills/*.md` for detailed procedures, `.claude/settings.json` for enforceable permissions.

**Structure**:
- `CLAUDE.md`: repo-wide conventions, commands, prerequisites (200-line soft budget)
- `.claude/rules/`: one file per path-scoped rule, with `paths` frontmatter for glob-based activation
- `.claude/skills/`: detailed playbooks
- `.claude/settings.json`: `permissions.deny` entries for enforceable guardrails

**Path-scoped rules**: each file in `.claude/rules/` has frontmatter specifying which paths activate it:
```yaml
---
paths:
  - "src/payments/**"
---
```

**Permissions**: guardrail claims that match enforceable patterns (e.g., "never run `rm -rf`") are projected as `permissions.deny` entries in `settings.json`, which Claude Code enforces at runtime.

## Copilot (Beta)

**Output files**: `.github/copilot-instructions.md`, `.github/.instructions.md` files with `applyTo` frontmatter, `copilot-setup-steps.yml` for environment setup, tool configuration.

**Structure**:
- `copilot-instructions.md`: repo-wide conventions and commands (300-line soft budget)
- `.instructions.md` files: path-scoped rules with `applyTo` globs
- `copilot-setup-steps.yml`: environment setup commands with constraint validation (supported keys, job naming, timeouts)

**Tool allowlist**: guardrail claims about allowed/denied tools are projected as tool configuration for Copilot's MCP integration.

**Known gaps**: Copilot supports tools-only MCP (no resources or prompts). Some RKP features that rely on MCP resources are unavailable.

## Cursor (Alpha)

**Output files**: `.cursor/rules/*.mdc` with frontmatter.

**Structure**: each rule file has frontmatter controlling activation:
```yaml
---
alwaysApply: true
globs: ["src/**/*.py"]
---
```

**Limitations**: no skills support, no permissions enforcement, no environment config. Export-only in Phase 1.

## Windsurf (Alpha)

**Output files**: `.windsurf/rules/*.md` with trigger frontmatter.

**Structure**: each rule file has frontmatter controlling trigger:
```yaml
---
trigger: always
---
```

**Budget**: 6 KiB hard limit per rule file, 12 KiB workspace total. These are tight — only the highest-priority claims fit.

**Deduplication**: Windsurf auto-reads AGENTS.md, so the adapter identifies claims already projected to AGENTS.md and excludes them from `.windsurf/rules/` to avoid duplication.

**Limitations**: no skills support, no permissions enforcement, no environment config. Export-only in Phase 1.

## Context Budget Tracking

Each adapter has size constraints defined in `projection/capability_matrix.py`. The `BudgetTracker` monitors content size during projection:

- **Hard budget**: absolute byte limit. Content beyond this is excluded with an overflow report.
- **Soft budget**: advisory line limit. Content beyond this triggers warnings but isn't truncated.
- **Workspace budget**: total across all rule files (Windsurf-specific).

Overflow routing: when content exceeds the always-on budget, it's pushed to skills files. If skills aren't supported by the host, it's excluded with documentation in the overflow report.

## Sensitivity Filtering Per Host

All hosts receive the same sensitivity filtering — `team-only` and `local-only` claims are excluded. This filtering happens at a single enforcement point (`projection/sensitivity.py`) before any adapter sees the claims. The adapter never makes sensitivity decisions.
