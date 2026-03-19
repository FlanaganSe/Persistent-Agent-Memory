# Quality Harness

The quality harness is RKP's formal measurement system — the mechanism by which adapter maturity is earned and extraction quality is tracked.

## Purpose

The harness answers: "Does RKP extract the right claims, project them correctly, and never leak sensitive data?" It runs five evaluation suites plus optional performance benchmarks.

## Components

### 1. Fixture Evaluation (Precision/Recall)

Compares extracted claims against expected claims defined in `expected_claims.json` files within fixture repos.

- **Precision**: what fraction of extracted claims are correct
- **Recall**: what fraction of expected claims were found
- **F1 score**: harmonic mean of precision and recall
- **Gate**: F1 >= 80% for each fixture

### 2. Export Conformance

Round-trip validation per adapter: extract claims from a fixture → project through adapter → validate output.

Checks:
- **Valid format**: output matches the host's expected structure
- **Within budget**: content fits the host's size constraints
- **Deterministic**: same claims produce identical output on repeated runs
- **Correct inclusion**: approved claims that should appear do appear
- **Correct exclusion**: suppressed/sensitive claims do not appear

Gate: >= 95% conformance score for GA adapters (AGENTS.md, CLAUDE.md).

### 3. Sensitivity Leakage Tests

Verifies that `team-only` and `local-only` claims never appear in projected output or MCP responses.

Tests all output boundaries:
- Projection to each adapter (AGENTS.md, CLAUDE.md, Copilot)
- MCP tool responses
- Response filter paths

Gate: zero leakage across all boundaries.

### 4. Drift Detection Tests

Uses the `with_drift` fixture to verify drift detection correctness:

- Pre-populated artifacts with known hashes
- Modified files that should trigger drift
- Expected drift count compared against detected drift count
- Validates false positive and false negative rates

### 5. Import Fidelity

Round-trip test: import an instruction file → produce claims → project back through the same adapter → measure content survival.

- Counts operational claims (commands, always-on rules, restrictions) that survive the round trip
- Gate: fidelity score >= 20% (conservative — import from multiple files, adapter projects a subset)

### 6. Performance Benchmarks (Optional)

Generates a synthetic repo of configurable size and benchmarks extraction time.

- Default target: 250k lines of code
- Gate: `rkp init` completes within 5 minutes
- Skippable via `--skip-performance`

## How to Run

```bash
# Full harness (skip performance)
nox -s quality

# CLI
rkp quality

# Direct invocation
python -m rkp.quality --fixtures tests/fixtures/ --report quality-report.json --skip-performance

# With performance benchmarks (slow)
python -m rkp.quality --fixtures tests/fixtures/ --report quality-report.json
```

## Fixture Repo Structure

Each fixture in `tests/fixtures/` is a minimal repo with known content:

```
tests/fixtures/
├── simple_python/          # Python project with pyproject.toml
│   ├── pyproject.toml
│   ├── src/
│   └── expected_claims.json
├── simple_js/              # JavaScript project with package.json
│   ├── package.json
│   ├── src/
│   └── expected_claims.json
├── with_agents_md/         # Repo with existing AGENTS.md (for import)
│   ├── AGENTS.md
│   └── expected_claims.json
├── with_ci/                # Repo with GitHub Actions workflows
│   ├── .github/workflows/
│   └── expected_claims.json
├── with_conflicts/         # Repo with known conflicts
│   └── expected_claims.json
└── with_drift/             # Repo with drift detection test data
    ├── drift_setup.json
    └── expected_claims.json
```

### expected_claims.json Format

```json
{
  "claims": [
    {
      "claim_type": "validated-command",
      "content_pattern": "pytest",
      "required": true,
      "source_authority": "executable-config"
    },
    {
      "claim_type": "always-on-rule",
      "content_pattern": "frozen dataclass",
      "required": false
    }
  ]
}
```

Each entry specifies:
- `claim_type`: expected type
- `content_pattern`: substring or regex to match against claim content
- `required`: whether missing this claim fails the fixture
- `source_authority` (optional): expected authority level

## Adapter Maturity Promotion Criteria

| Maturity | Conformance | Leakage | Drift | Additional |
|---|---|---|---|---|
| **GA** | >= 95% | Zero | Pass | Full format validation, budget compliance, deterministic output |
| **Beta** | Pass (with documented gaps) | Zero | Pass | Gaps explicitly documented |
| **Alpha** | Tests run | — | — | Export-only, gaps expected |

Promotion is assessed by `quality/promotion.py` after all harness components complete.

## Trace Capture

RKP logs MCP tool calls for quality analysis:

- **What's logged**: tool name, arguments, response status, claim count, response size, duration
- **Where**: `.rkp/local/traces/` (gitignored, local-only)
- **Format**: JSONL (one JSON object per line)
- **Control**: `trace_enabled` config option (default: true)

Traces are never transmitted off-machine. They exist for local debugging and quality analysis.

## How to Add New Fixtures

1. Create a directory in `tests/fixtures/` with representative source files
2. Add an `expected_claims.json` with the standardized format (must have a `"claims"` key)
3. Mark critical claims as `"required": true`
4. Run `nox -s quality` to verify the fixture evaluates correctly

## Quality Report

The harness produces a human-readable summary to stderr and an optional JSON report:

```
============================================================
RKP Quality Harness Report
============================================================

--- Extraction Precision/Recall ---
  simple_python: precision=87% recall=92% F1=89% [PASS]
  simple_js: precision=85% recall=88% F1=86% [PASS]

--- Export Conformance ---
  agents-md: score=98% format=OK budget=OK deterministic=YES
  claude: score=97% format=OK budget=OK deterministic=YES
  copilot: score=94% format=OK budget=OK deterministic=YES

--- Sensitivity Leakage ---
  15 boundaries checked, 0 leaked

--- Drift Detection ---
  with_drift: expected=2 detected=2 [PASS]

--- Import Fidelity ---
  AGENTS.md → agents-md: fidelity=65% (5/8 survived) [PASS]

--- Adapter Maturity Assessment ---
  agents-md: GA eligible ✓
  claude: GA eligible ✓
  copilot: Beta eligible ✓

============================================================
Overall: PASS
============================================================
```
