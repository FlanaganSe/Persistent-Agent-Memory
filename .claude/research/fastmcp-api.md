# FastMCP v3 API Research (Verified 2026-03-18)

**Package**: `fastmcp` v3.1.1 (standalone, PyPI), Apache-2.0. Docs: https://gofastmcp.com

## Server + Lifespan

```python
from fastmcp import FastMCP, Context
from fastmcp.server.lifespan import lifespan

@lifespan
async def app_lifespan(server):
    data = {"db": open_db()}
    try:
        yield data  # becomes ctx.lifespan_context
    finally:
        data["db"].close()

mcp = FastMCP("name", version="0.1.0", instructions="...", lifespan=app_lifespan)
```

Compose lifespans: `lifespan_a | lifespan_b` (left-to-right entry, merged dicts).
Run: `mcp.run()` (stdio) or `mcp.run(transport="http", host="0.0.0.0", port=9000)`.

## Tools with Annotations

```python
@mcp.tool(annotations={"readOnlyHint": True})
def my_tool(ctx: Context, param: str) -> dict:
    db = ctx.lifespan_context["db"]
    return {"result": "..."}
```

Or: `from mcp.types import ToolAnnotations` for typed annotations.
Other: `tags={"set"}`, `timeout=30.0`.

## Resources

```python
@mcp.resource("rkp://repo/overview")
def get_overview() -> str:
    return json.dumps({...})

@mcp.resource("rkp://repo/conventions/{path}")
def get_conventions(path: str) -> str:
    return json.dumps({...})
```

## Testing (In-Memory, No Subprocess)

```python
from fastmcp import FastMCP, Client
from mcp.types import TextContent

async def test_tool(server: FastMCP):
    async with Client(server) as client:
        result = await client.call_tool("my_tool", {"param": "value"})
        assert isinstance(result[0], TextContent)
```

**CRITICAL**: Do NOT create `Client` in pytest fixtures — causes event loop issues. Open inside test function body.

## Key Imports

```python
from fastmcp import FastMCP, Client, Context
from fastmcp.server.lifespan import lifespan
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations, TextContent
```
