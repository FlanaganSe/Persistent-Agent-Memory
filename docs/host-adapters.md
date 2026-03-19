# Host Adapters

RKP keeps one canonical claim model and projects it into host-native agent surfaces. The adapters are intentionally not symmetrical: each host gets the strongest faithful projection RKP can support today.

## Current adapter matrix

| Host | Files emitted today | Status |
|---|---|---|
| Codex | `AGENTS.md` | GA-eligible in the quality harness |
| Claude Code | `CLAUDE.md`, `.claude/rules/`, `.claude/skills/`, `.claude/settings-snippet.json` | GA-eligible in the quality harness |
| GitHub Copilot | `.github/copilot-instructions.md`, `.github/instructions/*.instructions.md`, `.github/workflows/copilot-setup-steps.yml`, `.copilot-tool-allowlist.json` | Beta |
| Cursor | `.cursor/rules/` | Alpha |
| Windsurf | `.windsurf/rules/` | Alpha |

## Important reality checks

- Codex support currently means a strong `AGENTS.md` projection. RKP does not yet emit Codex `.agents/skills/`.
- Claude currently emits a `settings-snippet`, not a full `.claude/settings.json`.
- Copilot setup steps live at `.github/workflows/copilot-setup-steps.yml`.
- Cursor and Windsurf are useful export surfaces, but not yet at the same confidence level as Codex and Claude.

## Projection rules

1. Preview includes unreviewed claims but hides suppressed and tombstoned claims.
2. Apply only writes approved or edited claims.
3. Sensitivity filtering runs before adapter-specific formatting.
4. Deterministic sorting keeps repeated projections stable.
5. Imported claims never outrank executable config until promoted by review.
6. Adapters format claims; they do not infer new claims.

## Host-specific notes

## Codex

- Output: root `AGENTS.md`
- Best for: concise always-on repo guidance and validated command lists
- Current limitation: no projected Codex skills yet

## Claude Code

- Strongest multi-file surface today
- Supports scoped rules, skill-style playbooks, and permission-deny snippets
- The emitted settings artifact is intentionally a snippet for human-controlled merge into broader Claude config

## GitHub Copilot

- Thin main instructions file to avoid duplicating repo-wide guidance
- Path-scoped `.instructions.md` support
- Constraint-validated `copilot-setup-steps.yml`
- Conservative MCP tool allowlist snippet

## Cursor

- Export-only alpha path
- Useful for scoped markdown rule generation
- No separate skills or settings projection

## Windsurf

- Export-only alpha path
- Deduplicates content already projected into `AGENTS.md`
- Tight workspace budget means only the highest-priority claims fit
