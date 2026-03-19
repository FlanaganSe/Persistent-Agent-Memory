# Demo Walkthrough

This is the highest-signal demo path for RKP today. It shows extraction, governance, projection, and MCP access without pretending the product is more finished than it is.

## Demo goals

- Show that repo knowledge is extracted from evidence, not invented
- Show that human review gates what gets written
- Show that the same governed knowledge is available through CLI preview and MCP

## Script

### 1. Validate the environment

```bash
rkp doctor
```

### 2. Initialize and inspect

```bash
rkp init
rkp status
```

Call out:

- `.rkp/config.yaml` is checked in
- `.rkp/local/rkp.db` is local cache
- claims, freshness, and drift are tracked explicitly

### 3. Preview a projection

```bash
rkp preview --host codex
```

Or for a richer surface:

```bash
rkp preview --host claude
```

### 4. Govern the claims

```bash
rkp review --approve-all --threshold 0.95
```

Then show:

```bash
rkp status
```

### 5. Write reviewed output

```bash
rkp apply --host claude --yes
```

Call out that `apply` writes only reviewed claims.

### 6. Expose live context over MCP

```bash
rkp serve
```

If you want one concrete MCP question to demonstrate:

- `get_preflight_context(path_or_symbol="src/rkp/server", host="claude")`
- `get_instruction_preview(consumer="codex")`
- `get_guardrails(path_or_scope="**")`

## Good demo framing

- “RKP is the source-of-truth layer, not another assistant UI.”
- “The durable value is governed repo knowledge, not one more instruction file generator.”
- “The product is alpha, but the trust boundaries are already intentional.”
