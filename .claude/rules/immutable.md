---
description: Non-negotiable project rules. Violations must be flagged immediately.
---
# Immutable Rules

1. **No instruction file written without human review** — AC-10. The apply command gates on review_state.
2. **All YAML via safe_load or strictyaml** — Never yaml.load(). Security invariant from M1.
3. **Sensitivity filter at every output boundary** — Single enforcement point pattern. Found and fixed a gap in M10.
4. **Claim IDs are immutable after creation** — Edits change content, not ID. ADR in decisions.md.
5. **Imported claims do not outrank executable-config** — DECLARED_IMPORTED_UNREVIEWED at precedence 3.5.
6. **stdout reserved for MCP protocol** — All logging and diagnostics to stderr.
7. **Adapter maturity earned via conformance harness** — No GA/Beta labels without M13 passing.
8. **tree-sitter v0.25+ QueryCursor API** — Old query.captures() is removed. Use QueryCursor.
9. **local-only claims never in .rkp/overrides/** — Only in .rkp/local/ DB.
10. **MCP tools are read-only except refresh_index** — refresh_index has readOnlyHint: false.
