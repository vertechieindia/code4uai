"""Main CLI entry point."""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from .commands import refactor, analyze, generate, chat, config, agent

app = typer.Typer(
    name="code4u",
    help="code4u.ai CLI - AI-powered code engineering from your terminal",
    add_completion=True,
    rich_markup_mode="rich",
)

console = Console()

# Register command groups
app.add_typer(refactor.app, name="refactor", help="Refactor code with AI")
app.add_typer(analyze.app, name="analyze", help="Analyze code impact and dependencies")
app.add_typer(generate.app, name="generate", help="Generate code from descriptions")
app.add_typer(chat.app, name="chat", help="Chat with the AI agent")
app.add_typer(config.app, name="config", help="Manage configuration")
app.add_typer(agent.app, name="agent", help="Run autonomous agents")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Show version"),
):
    """code4u.ai - AI-powered code engineering from your terminal."""
    if version:
        from . import __version__
        console.print(f"code4u.ai CLI v{__version__}")
        raise typer.Exit()
    
    if ctx.invoked_subcommand is None:
        console.print(Panel(
            Markdown("""
# code4u.ai CLI

**AI-powered code engineering from your terminal.**

## Quick Start

```bash
# Refactor code
code4u refactor "rename email to primaryEmail" --file users.py

# Analyze impact
code4u analyze impact --file api/routes.py

# Generate code
code4u generate "add authentication middleware"

# Start interactive chat
code4u chat

# Run autonomous agent
code4u agent run "implement dark mode feature"
```

## Commands

- `refactor` - Safe, validated code refactoring
- `analyze` - Impact analysis and dependency mapping
- `generate` - Generate code from descriptions
- `chat` - Interactive AI chat
- `agent` - Run autonomous agents
- `config` - Manage settings

Use `code4u <command> --help` for more info.
            """),
            title="🚀 code4u.ai",
            border_style="cyan",
        ))


if __name__ == "__main__":
    app()

