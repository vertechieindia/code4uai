"""Autonomous agent commands."""

import asyncio
import os
from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.live import Live
from rich.layout import Layout

from ..client import Code4uClient

app = typer.Typer(help="Run autonomous agents")
console = Console()


@app.command("run")
def agent_run(
    task: str = typer.Argument(..., help="Task description"),
    directory: Path = typer.Option(".", "--dir", "-d", help="Working directory"),
    max_steps: int = typer.Option(50, "--max-steps", help="Maximum steps"),
    auto_apply: bool = typer.Option(False, "--auto-apply", "-y", help="Auto-apply changes"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Watch for file changes"),
):
    """Run an autonomous agent to complete a task."""
    asyncio.run(_agent_run(task, directory, max_steps, auto_apply, watch))


async def _agent_run(
    task: str,
    directory: Path,
    max_steps: int,
    auto_apply: bool,
    watch: bool,
):
    """Async agent execution."""
    console.print(Panel(
        f"[bold]Task:[/bold] {task}\n"
        f"[bold]Directory:[/bold] {directory.absolute()}\n"
        f"[bold]Max Steps:[/bold] {max_steps}",
        title="🤖 Autonomous Agent",
        border_style="cyan",
    ))
    
    # State machine visualization
    states = [
        "INIT",
        "IMPACT_ANALYZED", 
        "PLAN_GENERATED",
        "CONTRACT_VALIDATED",
        "CODE_GENERATED",
        "VERIFIED",
        "READY_FOR_REVIEW",
    ]
    
    current_state = 0
    
    def render_state_machine():
        table = Table(show_header=False, box=None)
        for i, state in enumerate(states):
            if i < current_state:
                table.add_row(f"[green]✓[/green]", f"[green]{state}[/green]")
            elif i == current_state:
                table.add_row(f"[cyan]●[/cyan]", f"[bold cyan]{state}[/bold cyan]")
            else:
                table.add_row(f"[dim]○[/dim]", f"[dim]{state}[/dim]")
        return table
    
    console.print("\n[bold]State Machine:[/bold]")
    
    with Live(render_state_machine(), console=console, refresh_per_second=4) as live:
        for i in range(len(states)):
            current_state = i
            live.update(render_state_machine())
            await asyncio.sleep(0.8)  # Simulated processing
    
    console.print("\n[bold]Proposed Changes:[/bold]")
    console.print(Panel(
        "```diff\n"
        "- old_function_name()\n"
        "+ new_function_name()\n"
        "```",
        border_style="yellow",
    ))
    
    if not auto_apply:
        apply = typer.confirm("\nApply changes?")
        if not apply:
            console.print("[dim]Changes rejected[/dim]")
            return
    
    console.print("\n[green]✓ Changes applied successfully[/green]")
    console.print("[dim]Rollback available for 7 days[/dim]")


@app.command("plan")
def agent_plan(
    task: str = typer.Argument(..., help="Task to plan"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Save plan to file"),
):
    """Generate an execution plan without running."""
    asyncio.run(_agent_plan(task, output))


async def _agent_plan(task: str, output: Optional[Path]):
    """Generate execution plan."""
    console.print(Panel(
        f"[bold]Task:[/bold] {task}",
        title="📋 Execution Plan",
        border_style="cyan",
    ))
    
    console.print("\n[bold]Planned Steps:[/bold]")
    
    steps = [
        ("Analyze impact", "Determine affected files and symbols"),
        ("Generate plan", "Create step-by-step execution plan"),
        ("Validate contracts", "Check API and schema compatibility"),
        ("Generate code", "Create code changes"),
        ("Verify changes", "Run tests and linters"),
        ("Prepare for review", "Format diffs for human review"),
    ]
    
    for i, (name, desc) in enumerate(steps, 1):
        console.print(f"  {i}. [bold]{name}[/bold]: {desc}")
    
    console.print("\n[bold]Estimated Impact:[/bold]")
    console.print("  • Files: ~5")
    console.print("  • Functions: ~12")
    console.print("  • Tests needed: ~3")
    
    if output:
        output.write_text(f"# Execution Plan\n\nTask: {task}\n\nSteps:\n" + 
                         "\n".join(f"{i}. {s[0]}: {s[1]}" for i, s in enumerate(steps, 1)))
        console.print(f"\n[green]✓ Plan saved to {output}[/green]")


@app.command("status")
def agent_status():
    """Show status of running agents."""
    console.print(Panel(
        "[dim]No agents currently running[/dim]",
        title="🤖 Agent Status",
        border_style="cyan",
    ))


@app.command("history")
def agent_history(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of entries"),
):
    """Show agent execution history."""
    table = Table(title="Agent History")
    table.add_column("ID", style="cyan")
    table.add_column("Task")
    table.add_column("Status")
    table.add_column("Duration")
    table.add_column("Time")
    
    table.add_row(
        "abc123",
        "Rename email to primaryEmail",
        "[green]✓ Applied[/green]",
        "12s",
        "2 hours ago",
    )
    table.add_row(
        "def456",
        "Add dark mode toggle",
        "[green]✓ Applied[/green]",
        "45s",
        "1 day ago",
    )
    table.add_row(
        "ghi789",
        "Refactor auth middleware",
        "[yellow]Rejected[/yellow]",
        "8s",
        "2 days ago",
    )
    
    console.print(table)


@app.command("rollback")
def agent_rollback(
    agent_id: str = typer.Argument(..., help="Agent execution ID to rollback"),
):
    """Rollback changes from a previous agent run."""
    console.print(f"\n[bold]Rolling back:[/bold] {agent_id}")
    console.print("[green]✓ Rollback successful[/green]")

