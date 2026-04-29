"""Analyze commands."""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..client import Code4uClient

app = typer.Typer(help="Analyze code impact and dependencies")
console = Console()


@app.command("impact")
def analyze_impact(
    file: Path = typer.Option(..., "--file", "-f", help="File to analyze"),
    symbol: Optional[str] = typer.Option(None, "--symbol", "-s", help="Specific symbol"),
    depth: int = typer.Option(5, "--depth", "-d", help="Analysis depth"),
):
    """Analyze the impact of changes to a file or symbol."""
    asyncio.run(_analyze_impact(file, symbol, depth))


async def _analyze_impact(file: Path, symbol: Optional[str], depth: int):
    """Async impact analysis."""
    if not file.exists():
        console.print(f"[red]Error: File not found: {file}[/red]")
        raise typer.Exit(1)
    
    console.print(Panel(
        f"[bold]File:[/bold] {file}" + (f"\n[bold]Symbol:[/bold] {symbol}" if symbol else ""),
        title="🔍 Impact Analysis",
        border_style="cyan",
    ))
    
    async with Code4uClient() as client:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Analyzing dependencies...", total=None)
            
            try:
                result = await client.analyze_impact(str(file), symbol)
                progress.update(task, description="Complete!")
            except Exception as e:
                progress.update(task, description="Failed!")
                console.print(f"[red]Error: {e}[/red]")
                raise typer.Exit(1)
    
    # Risk level
    risk = result.get("risk_level", "low")
    risk_colors = {"low": "green", "medium": "yellow", "high": "red", "critical": "red bold"}
    console.print(f"\n[bold]Risk Level:[/bold] [{risk_colors.get(risk, 'white')}]{risk.upper()}[/]")
    
    if result.get("breaking_change"):
        console.print("[red bold]⚠️  BREAKING CHANGE[/red bold]")
    
    # Stats table
    table = Table(title="Impact Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right")
    
    table.add_row("Files affected", str(len(result.get("impacted_files", []))))
    table.add_row("Functions affected", str(len(result.get("impacted_functions", []))))
    table.add_row("Classes affected", str(len(result.get("impacted_classes", []))))
    table.add_row("Teams affected", str(len(result.get("impacted_teams", []))))
    table.add_row("Direct dependencies", str(len(result.get("directly_impacted", []))))
    table.add_row("Transitive dependencies", str(len(result.get("transitively_impacted", []))))
    
    console.print(table)
    
    # Impacted files
    files = result.get("impacted_files", [])
    if files:
        console.print("\n[bold]Impacted Files:[/bold]")
        for f in files[:10]:
            console.print(f"  • {f}")
        if len(files) > 10:
            console.print(f"  [dim]... and {len(files) - 10} more[/dim]")
    
    # Teams
    teams = result.get("impacted_teams", [])
    if teams:
        console.print(f"\n[bold]Teams to notify:[/bold] {', '.join(teams)}")
    
    # Recommendations
    recs = result.get("recommendations", [])
    if recs:
        console.print("\n[bold]Recommendations:[/bold]")
        for rec in recs:
            console.print(f"  → {rec}")


@app.command("deps")
def analyze_deps(
    file: Path = typer.Option(..., "--file", "-f", help="File to analyze"),
    direction: str = typer.Option("both", "--direction", "-d", help="in/out/both"),
):
    """Show dependencies for a file."""
    asyncio.run(_analyze_deps(file, direction))


async def _analyze_deps(file: Path, direction: str):
    """Async dependency analysis."""
    console.print(Panel(
        f"[bold]File:[/bold] {file}\n[bold]Direction:[/bold] {direction}",
        title="📊 Dependency Analysis",
        border_style="cyan",
    ))
    
    console.print("\n[dim]Dependency tree analysis would be shown here[/dim]")
    
    # Build tree visualization
    tree = Tree(f"📄 {file.name}")
    imports = tree.add("📥 Imports (Dependencies)")
    imports.add("utils.py")
    imports.add("models.py")
    
    dependents = tree.add("📤 Dependents (Used by)")
    dependents.add("api/routes.py")
    dependents.add("tests/test_file.py")
    
    console.print(tree)


@app.command("index")
def analyze_index(
    directory: Path = typer.Argument(".", help="Directory to index"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r", help="Recurse into subdirectories"),
):
    """Index a directory for the Knowledge Graph."""
    asyncio.run(_analyze_index(directory, recursive))


async def _analyze_index(directory: Path, recursive: bool):
    """Async indexing."""
    if not directory.exists():
        console.print(f"[red]Error: Directory not found: {directory}[/red]")
        raise typer.Exit(1)
    
    console.print(Panel(
        f"[bold]Directory:[/bold] {directory.absolute()}",
        title="📚 Indexing",
        border_style="cyan",
    ))
    
    async with Code4uClient() as client:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Indexing files...", total=None)
            
            try:
                result = await client.index_directory(str(directory.absolute()), recursive)
                progress.update(task, description="Complete!")
            except Exception as e:
                progress.update(task, description="Failed!")
                console.print(f"[red]Error: {e}[/red]")
                raise typer.Exit(1)
    
    # Show stats
    table = Table(title="Indexing Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right")
    
    table.add_row("Files indexed", str(result.get("files_indexed", 0)))
    table.add_row("Nodes created", str(result.get("nodes_created", 0)))
    table.add_row("Relationships", str(result.get("relationships_created", 0)))
    table.add_row("Errors", str(result.get("errors", 0)))
    
    console.print(table)
    console.print("\n[green]✓ Knowledge Graph updated[/green]")

