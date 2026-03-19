# Testing

RKP’s verification story matters because the product is fundamentally about trust.

## Main test commands

```bash
uv run nox -s lint
uv run nox -s typecheck
uv run nox -s test
uv run nox -s quality
uv run nox -s docs
```

## What each layer proves

- `lint`: style, imports, and formatting drift
- `typecheck`: strict pyright validation on the source tree
- `test`: unit, integration, property, and snapshot coverage
- `quality`: adapter conformance, sensitivity leakage, drift handling, and import fidelity
- `docs`: MkDocs build integrity and navigation correctness

## Useful targeted runs

```bash
uv run pytest tests/integration/test_mcp_*.py
uv run pytest tests/integration/test_cli_*.py
uv run pytest tests/unit/test_docs_evidence.py
uv run pytest tests/unit/test_logging.py
```

## What is and is not covered today

Covered:

- CLI lifecycle and projection flows
- MCP tool/resource envelopes
- projection determinism and budget handling
- sensitivity leakage checks
- import fidelity

Not fully covered yet:

- broader real-world repo fixtures beyond the curated test set
- remote MCP transport scenarios
- sandbox verification for commands

The quality harness is the most important trust signal for adapter maturity; it is not just extra test decoration.
