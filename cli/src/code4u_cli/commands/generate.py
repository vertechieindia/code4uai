"""Generate commands."""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..client import Code4uClient

app = typer.Typer(help="Generate code from descriptions")
console = Console()


@app.command("code")
def generate_code(
    description: str = typer.Argument(..., help="What to generate"),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="Output file"),
    language: str = typer.Option("python", "--lang", "-l", help="Programming language"),
    context: Optional[Path] = typer.Option(None, "--context", "-c", help="Context file"),
):
    """Generate code from a description."""
    asyncio.run(_generate_code(description, file, language, context))


async def _generate_code(
    description: str,
    file: Optional[Path],
    language: str,
    context: Optional[Path],
):
    """Async code generation."""
    console.print(Panel(
        f"[bold]Description:[/bold] {description}\n[bold]Language:[/bold] {language}",
        title="✨ Code Generation",
        border_style="cyan",
    ))
    
    async with Code4uClient() as client:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Generating code...", total=None)
            
            try:
                # Call refactor API with generate intent
                result = await client.refactor(
                    intent=f"Generate: {description}",
                    file_path=str(file) if file else "generated.py",
                )
                progress.update(task, description="Complete!")
            except Exception as e:
                progress.update(task, description="Failed!")
                console.print(f"[red]Error: {e}[/red]")
                raise typer.Exit(1)
    
    # Show generated code
    code = result.get("generated_code", result.get("diff", "# No code generated"))
    console.print("\n[bold]Generated Code:[/bold]")
    console.print(Syntax(code, language, theme="monokai", line_numbers=True))
    
    if file:
        if file.exists():
            overwrite = typer.confirm(f"File {file} exists. Overwrite?")
            if not overwrite:
                console.print("[dim]Cancelled[/dim]")
                return
        
        file.write_text(code)
        console.print(f"\n[green]✓ Written to {file}[/green]")


@app.command("test")
def generate_test(
    file: Path = typer.Option(..., "--file", "-f", help="File to generate tests for"),
    framework: str = typer.Option("pytest", "--framework", help="Test framework"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
):
    """Generate tests for a file."""
    description = f"Generate {framework} tests for {file}"
    asyncio.run(_generate_code(description, output or Path(f"test_{file.stem}.py"), "python", file))


@app.command("api")
def generate_api(
    spec: str = typer.Argument(..., help="API specification"),
    framework: str = typer.Option("fastapi", "--framework", help="Web framework"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
):
    """Generate API endpoint from specification."""
    description = f"Generate {framework} API endpoint: {spec}"
    asyncio.run(_generate_code(description, output, "python", None))


@app.command("component")
def generate_component(
    name: str = typer.Argument(..., help="Component name"),
    framework: str = typer.Option("react", "--framework", help="UI framework"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
):
    """Generate UI component."""
    lang = "typescript" if framework in ["react", "vue", "angular"] else "python"
    ext = ".tsx" if framework == "react" else ".py"
    description = f"Generate {framework} component named {name}"
    asyncio.run(_generate_code(description, output or Path(f"{name}{ext}"), lang, None))

