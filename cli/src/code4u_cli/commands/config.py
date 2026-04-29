"""Configuration commands."""

import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(help="Manage configuration")
console = Console()

CONFIG_FILE = Path.home() / ".config" / "code4u" / "config.toml"


@app.command("show")
def config_show():
    """Show current configuration."""
    console.print(Panel(
        "[bold]Current Configuration[/bold]",
        title="⚙️  code4u.ai Config",
        border_style="cyan",
    ))
    
    table = Table(show_header=True)
    table.add_column("Setting", style="cyan")
    table.add_column("Value")
    table.add_column("Source", style="dim")
    
    table.add_row(
        "server_url",
        os.getenv("CODE4U_SERVER_URL", "http://localhost:8002"),
        "env" if os.getenv("CODE4U_SERVER_URL") else "default",
    )
    table.add_row(
        "api_key",
        "****" + os.getenv("CODE4U_API_KEY", "")[-4:] if os.getenv("CODE4U_API_KEY") else "[dim]not set[/dim]",
        "env" if os.getenv("CODE4U_API_KEY") else "-",
    )
    table.add_row(
        "tenant_id",
        os.getenv("CODE4U_TENANT_ID", "default"),
        "env" if os.getenv("CODE4U_TENANT_ID") else "default",
    )
    table.add_row(
        "config_file",
        str(CONFIG_FILE),
        "exists" if CONFIG_FILE.exists() else "[dim]not found[/dim]",
    )
    
    console.print(table)


@app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Configuration key"),
    value: str = typer.Argument(..., help="Configuration value"),
):
    """Set a configuration value."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Simple key-value storage
    config = {}
    if CONFIG_FILE.exists():
        import tomllib
        with open(CONFIG_FILE, "rb") as f:
            config = tomllib.load(f)
    
    config[key] = value
    
    # Write back (simple format)
    with open(CONFIG_FILE, "w") as f:
        for k, v in config.items():
            f.write(f'{k} = "{v}"\n')
    
    console.print(f"[green]✓ Set {key} = {value}[/green]")


@app.command("get")
def config_get(
    key: str = typer.Argument(..., help="Configuration key"),
):
    """Get a configuration value."""
    # Check environment first
    env_key = f"CODE4U_{key.upper()}"
    if env_key in os.environ:
        console.print(os.environ[env_key])
        return
    
    # Check config file
    if CONFIG_FILE.exists():
        import tomllib
        with open(CONFIG_FILE, "rb") as f:
            config = tomllib.load(f)
        if key in config:
            console.print(config[key])
            return
    
    console.print(f"[red]Key not found: {key}[/red]")
    raise typer.Exit(1)


@app.command("init")
def config_init():
    """Initialize configuration interactively."""
    console.print(Panel(
        "Let's configure code4u.ai CLI",
        title="⚙️  Setup",
        border_style="cyan",
    ))
    
    server_url = typer.prompt(
        "Server URL",
        default="http://localhost:8002",
    )
    
    api_key = typer.prompt(
        "API Key (leave empty for local)",
        default="",
        show_default=False,
    )
    
    tenant_id = typer.prompt(
        "Tenant ID",
        default="default",
    )
    
    # Save config
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    with open(CONFIG_FILE, "w") as f:
        f.write(f'server_url = "{server_url}"\n')
        if api_key:
            f.write(f'api_key = "{api_key}"\n')
        f.write(f'tenant_id = "{tenant_id}"\n')
    
    console.print(f"\n[green]✓ Configuration saved to {CONFIG_FILE}[/green]")
    
    console.print("\n[bold]Next steps:[/bold]")
    console.print("  1. Run [cyan]code4u analyze index .[/cyan] to index your codebase")
    console.print("  2. Run [cyan]code4u chat[/cyan] to start chatting with the AI")
    console.print("  3. Run [cyan]code4u refactor[/cyan] to refactor code")


@app.command("path")
def config_path():
    """Show configuration file path."""
    console.print(str(CONFIG_FILE))

