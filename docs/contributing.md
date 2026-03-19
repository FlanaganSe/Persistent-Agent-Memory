# Contributing

RKP is still moving quickly. Contributions should preserve the core invariants, tighten docs/tests, and avoid speculative architecture.

## First steps

```bash
git clone https://github.com/seanflanagan/repo-knowledge-plane.git
cd repo-knowledge-plane
uv pip install ".[dev]"
```

## The minimum local check set

```bash
uv run nox -s lint
uv run nox -s typecheck
uv run nox -s test
uv run nox -s quality
uv run nox -s docs
```

Or run the bundled set:

```bash
uv run nox -s ci
```

## Contribution expectations

- Keep `stdout` safe for MCP and machine-readable output.
- Do not use `yaml.load()`.
- Preserve sensitivity filtering and review gating.
- Do not let imported claims outrank executable config by accident.
- Add tests for behavior changes.
- Update docs when command behavior, outputs, or maturity claims change.

## Good contribution targets

- correctness fixes with regression tests
- docs that match reality more closely
- adapter conformance improvements
- MCP/read-model improvements that preserve output boundaries
- better local developer and demo ergonomics

## Bad contribution targets

- hosted platform assumptions
- premature plugin systems
- broad rewrites that erase the current layered architecture
- features that bypass governance or trust-boundary rules

## Where to look next

- [Architecture](architecture.md)
- [Development guide](development.md)
- [Testing guide](testing.md)
- [Quality harness](quality-harness.md)
