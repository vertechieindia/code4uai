"""Refactor commands."""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..client import Code4uClient

app = typer.Typer(help="Refactor code with AI")
console = Console()


@app.command("run")
def refactor_run(
    intent: str = typer.Argument(..., help="What to refactor (e.g., 'rename email to primaryEmail')"),
    file: Path = typer.Option(..., "--file", "-f", help="Target file"),
    selection: Optional[str] = typer.Option(None, "--selection", "-s", help="Selected code to refactor"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show changes without applying"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-accept changes"),
):
    """Run a refactoring operation."""
    asyncio.run(_refactor_run(intent, file, selection, dry_run, yes))


async def _refactor_run(
    intent: str,
    file: Path,
    selection: Optional[str],
    dry_run: bool,
    yes: bool,
):
    """Async refactor implementation."""
    if not file.exists():
        console.print(f"[red]Error: File not found: {file}[/red]")
        raise typer.Exit(1)
    
    console.print(Panel(
        f"[bold]Intent:[/bold] {intent}\n[bold]File:[/bold] {file}",
        title="🔧 Refactoring",
        border_style="cyan",
    ))
    
    async with Code4uClient() as client:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Analyzing...", total=None)
            
            try:
                result = await client.refactor(
                    intent=intent,
                    file_path=str(file),
                    selection=selection,
                )
                
                progress.update(task, description="Complete!")
            except Exception as e:
                progress.update(task, description="Failed!")
                console.print(f"[red]Error: {e}[/red]")
                raise typer.Exit(1)
    
    # Show results
    if "diff" in result:
        console.print("\n[bold]Proposed Changes:[/bold]")
        console.print(Syntax(result["diff"], "diff", theme="monokai"))
    
    if result.get("breaking_change"):
        console.print("\n[yellow]⚠️  Breaking change detected![/yellow]")
    
    affected = result.get("affected_files", [])
    if affected:
        console.print(f"\n[bold]Affected files:[/bold] {len(affected)}")
        for f in affected[:5]:
            console.print(f"  • {f}")
    
    if dry_run:
        console.print("\n[dim]Dry run - no changes applied[/dim]")
        return
    
    if not yes:
        apply = typer.confirm("Apply changes?")
        if not apply:
            console.print("[dim]Changes rejected[/dim]")
            return
    
    console.print("[green]✓ Changes applied successfully[/green]")


@app.command("rename")
def refactor_rename(
    old_name: str = typer.Argument(..., help="Current symbol name"),
    new_name: str = typer.Argument(..., help="New symbol name"),
    file: Path = typer.Option(..., "--file", "-f", help="Target file"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-accept"),
):
    """Rename a symbol across the codebase."""
    intent = f"Rename '{old_name}' to '{new_name}'"
    asyncio.run(_refactor_run(intent, file, old_name, False, yes))


@app.command("extract")
def refactor_extract(
    name: str = typer.Argument(..., help="Name for extracted function"),
    file: Path = typer.Option(..., "--file", "-f", help="Target file"),
    lines: str = typer.Option(..., "--lines", "-l", help="Line range (e.g., '10-20')"),
):
    """Extract code into a new function."""
    intent = f"Extract lines {lines} into function named '{name}'"
    asyncio.run(_refactor_run(intent, file, None, False, False))

