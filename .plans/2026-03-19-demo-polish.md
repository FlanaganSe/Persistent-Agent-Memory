# Demo Polish Plan

Date: 2026-03-19

## Audit Themes

- Fix trust-boundary regressions first: stdout logging discipline, MCP allowlist parity, preview/resource visibility, and import/apply path drift.
- Prefer repo hygiene over new features: docs accuracy, CI/docs/release consistency, packaging metadata, and clearer setup/testing guidance.
- Keep product claims honest: RKP is an alpha product with strong adapter-quality signals, not a productionized hosted platform.

## Priorities

### P0

- Route diagnostics to stderr reliably so MCP stdout stays protocol-safe.
- Enforce the configured allowlist consistently across MCP tools and resources.
- Remove projection/import path drift for Copilot setup steps.
- Correct docs that misstate current adapter outputs or maturity.

### P1

- Make repo-local config exclusions work consistently during init, doctor, status, preview, serve, and refresh.
- Add regression tests for the new output-boundary behavior.
- Add docs and quality checks to the default local/CI verification path.
- Tighten release automation with version/tag and changelog preflight.

### P2

- Improve distribution/discoverability metadata.
- Add sharper demo and contributor guidance.
- Reduce self-index noise for this repository with repo-local exclusions.

## Explicit Non-Goals

- No hosted deployment architecture.
- No change to claim IDs, authority ordering, or review semantics.
- No new abstraction layers or speculative platform work.
