# Typer v0.24.1 API Research (Verified 2026-03-18)

## Multi-Command App with Subcommands

```python
import typer

app = typer.Typer(rich_markup_mode="rich", no_args_is_help=True)

# Mount subcommand groups
app.add_typer(init_app, name="init")
app.add_typer(review_app, name="review")

# Or merge to top-level (no name= argument, v0.15+)
app.add_typer(serve_app)
```

## Composition Root / DI via ctx.obj

```python
from dataclasses import dataclass

@dataclass
class AppState:
    db: Database
    verbose: bool = False

@app.callback()
def main(ctx: typer.Context, verbose: bool = False,
         repo: str = typer.Option(".", envvar="RKP_REPO")):
    ctx.obj = AppState(db=open_db(repo), verbose=verbose)

@app.command()
def status(ctx: typer.Context):
    state: AppState = ctx.obj
    # use state.db ...
```

## Rich Integration

```python
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import track, Progress, SpinnerColumn

console = Console(stderr=True)  # keep stdout for data

# Tables
table = Table(title="Claims")
table.add_column("ID", style="cyan")
table.add_row("claim-001")
console.print(table)

# Progress
for item in track(files, description="Parsing..."):
    process(item)
```

## Interactive Prompts (Review Flow)

```python
from rich.prompt import Prompt, Confirm

action = Prompt.ask("Action", choices=["approve", "edit", "suppress", "skip"], default="skip")
proceed = Confirm.ask("Apply changes?")

# Typer built-in
name = typer.prompt("Claim content")
typer.confirm("Are you sure?", abort=True)
```

## Testing

```python
from typer.testing import CliRunner

runner = CliRunner()
result = runner.invoke(app, ["status", "--json"])
assert result.exit_code == 0
```

## Exit Codes

`typer.Exit(code=0)` for clean exit, `typer.Abort()` for cancelled.
