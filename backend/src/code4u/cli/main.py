"""code4u CLI — typer + rich terminal interface.

Runs the full refactoring pipeline **locally** without requiring the
HTTP server.  Every command calls the indexer, context compiler, and
PlanExecutor directly.

Usage::

    code4u index [PATH]          Index a workspace and show stats.
    code4u refactor INTENT FILE  Run a full refactor pipeline.
    code4u rename OLD NEW FILE   Rename a symbol across all callers.
    code4u health [PATH]         Find unused symbols and offer to remove them.
    code4u cycles [PATH]         Detect circular import chains.
    code4u visual IMAGE          Map image visual elements to code symbols.
    code4u predict SYMBOL        Predict blast radius of modifying a symbol.
    code4u sessions              List recent refactoring sessions.
    code4u history               View refactor job history and analytics.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.syntax import Syntax

app = typer.Typer(
    name="code4u",
    help="code4u.ai — AI-native refactoring from your terminal.",
    add_completion=True,
    rich_markup_mode="rich",
    no_args_is_help=True,
)

console = Console()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_path(path: str) -> str:
    return str(Path(path).resolve())


def _run_async(coro):
    """Run an async coroutine from synchronous CLI context."""
    return asyncio.run(coro)


def _print_error(msg: str) -> None:
    console.print(f"[bold red]Error:[/bold red] {msg}")


def _print_success(msg: str) -> None:
    console.print(f"[bold green]Done:[/bold green] {msg}")


# ---------------------------------------------------------------------------
# code4u index
# ---------------------------------------------------------------------------

@app.command()
def index(
    path: str = typer.Argument(".", help="Workspace root to index."),
    no_cache: bool = typer.Option(False, "--no-cache", help="Force full re-parse (skip cache)."),
):
    """Index a workspace and display symbol statistics."""
    from code4u.code_intelligence.knowledge_graph.symbol_indexer import SymbolIndexer

    resolved = _resolve_path(path)
    if not Path(resolved).is_dir():
        _print_error(f"Not a directory: {resolved}")
        raise typer.Exit(1)

    indexer = SymbolIndexer()
    t0 = time.monotonic()
    dep_map = indexer.index_workspace(resolved, use_cache=not no_cache)
    elapsed = (time.monotonic() - t0) * 1000

    stats = dep_map.stats

    table = Table(title="Workspace Index", border_style="cyan")
    table.add_column("Metric", style="white")
    table.add_column("Value", style="bold cyan", justify="right")

    table.add_row("Workspace", resolved)
    table.add_row("Files indexed", str(stats["indexed_files"]))
    table.add_row("Total symbols", str(stats["total_symbols"]))
    table.add_row("Unique symbol names", str(stats["unique_symbol_names"]))
    table.add_row("Total imports", str(stats["total_imports"]))
    table.add_row("Reverse-dep entries", str(stats["reverse_dep_entries"]))
    table.add_row("Cache hits", str(stats["cache_hits"]))
    table.add_row("Cache misses", str(stats["cache_misses"]))
    table.add_row("Index time", f"{elapsed:.1f} ms")

    console.print(table)

    if stats["cache_hits"] > 0 and stats["cache_misses"] == 0:
        console.print(
            "[dim]All files served from cache — no re-parsing needed.[/dim]"
        )


# ---------------------------------------------------------------------------
# code4u rename
# ---------------------------------------------------------------------------

@app.command()
def rename(
    old_name: str = typer.Argument(..., help="Current symbol name."),
    new_name: str = typer.Argument(..., help="New symbol name."),
    file: str = typer.Argument(..., help="Primary file containing the symbol."),
    workspace: str = typer.Option(".", "--workspace", "-w", help="Workspace root."),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Preview without writing."),
):
    """Rename a symbol across all callers."""
    _run_refactor_pipeline(
        intent=f"Rename {old_name} to {new_name}",
        file_path=file,
        workspace_path=workspace,
        dry_run=dry_run,
    )


# ---------------------------------------------------------------------------
# code4u refactor
# ---------------------------------------------------------------------------

@app.command()
def refactor(
    intent: str = typer.Argument(..., help='Refactor intent, e.g. "Extract compute_total to math_utils.py".'),
    file: str = typer.Argument(..., help="Primary file path."),
    workspace: str = typer.Option(".", "--workspace", "-w", help="Workspace root."),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Preview without writing."),
):
    """Run a full refactor pipeline for a given intent."""
    _run_refactor_pipeline(
        intent=intent,
        file_path=file,
        workspace_path=workspace,
        dry_run=dry_run,
    )


def _run_refactor_pipeline(
    intent: str,
    file_path: str,
    workspace_path: str,
    dry_run: bool,
) -> None:
    """Shared pipeline runner for rename/refactor commands."""
    from code4u.code_intelligence.knowledge_graph.symbol_indexer import SymbolIndexer
    from code4u.code_intelligence.context.compiler import ContextCompiler
    from code4u.code_intelligence.context.planner import plan_from_blast_context
    from code4u.platform_core.agents.orchestrator import PlanExecutor

    ws = _resolve_path(workspace_path)
    fp = str(Path(file_path))
    if not Path(fp).is_absolute():
        fp = str((Path(ws) / fp).resolve())

    if not Path(fp).is_file():
        _print_error(f"File not found: {fp}")
        raise typer.Exit(1)

    console.print(f"[bold]Intent:[/bold] {intent}")
    console.print(f"[bold]File:[/bold]   {fp}")
    console.print(f"[bold]Root:[/bold]   {ws}")
    if dry_run:
        console.print("[bold yellow]Mode:[/bold yellow]   DRY RUN (no disk writes)")
    console.print()

    with console.status("[cyan]Indexing workspace...[/cyan]"):
        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace(ws)

    console.print(
        f"[dim]Indexed {dep_map.stats['indexed_files']} files "
        f"({dep_map.stats['total_symbols']} symbols) in "
        f"{dep_map.stats['index_time_ms']:.0f} ms[/dim]"
    )

    async def _run():
        compiler = ContextCompiler(dependency_map=dep_map)
        blast = await compiler.compile_refactor_blast_context(
            intent=intent,
            primary_file_path=fp,
            workspace_path=ws,
        )

        console.print(
            f"[dim]Affected files: {len(blast.affected_files)}[/dim]"
        )

        plan = plan_from_blast_context(blast)
        executor = PlanExecutor(dependency_map=dep_map, dry_run=dry_run)
        state = await executor.run(plan, blast, intent=intent)

        return executor, state

    try:
        with console.status("[cyan]Running pipeline...[/cyan]"):
            executor, state = _run_async(_run())
    except Exception as exc:
        _print_error(str(exc))
        raise typer.Exit(1)

    pp = executor.proposed_plan
    if pp:
        ops_table = Table(title="Proposed Plan", border_style="cyan")
        ops_table.add_column("Action", style="bold")
        ops_table.add_column("File", style="white")
        ops_table.add_column("Reason", style="dim")

        for op in pp.operations:
            action_color = {
                "edit": "yellow", "create": "green", "delete": "red"
            }.get(op.action, "white")
            short_path = "/".join(Path(op.file_path).parts[-3:])
            ops_table.add_row(
                f"[{action_color}]{op.action}[/{action_color}]",
                short_path,
                op.reason[:60],
            )
        console.print(ops_table)

        validation = (
            "[bold green]PASSED[/bold green]"
            if pp.validation_passed
            else "[bold red]FAILED[/bold red]"
        )
        console.print(f"Validation: {validation}")

    if executor.diffs:
        console.print()
        for fpath, diff in executor.diffs.items():
            if not diff.strip():
                continue
            short = "/".join(Path(fpath).parts[-3:])
            console.print(f"[bold]{short}[/bold]")
            console.print(Syntax(diff, "diff", theme="monokai", line_numbers=False))
            console.print()

    if state.value == "APPLIED":
        if dry_run:
            _print_success("Dry run complete — no files were modified.")
        else:
            _print_success(
                f"Refactor applied across {len(pp.operations) if pp else 0} file(s)."
            )
    else:
        _print_error(f"Pipeline ended in state: {state.value}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# code4u health
# ---------------------------------------------------------------------------

@app.command()
def health(
    path: str = typer.Argument(".", help="Workspace root to scan."),
    fix: bool = typer.Option(False, "--fix", "-f", help="Apply fixes automatically."),
    dry_run: bool = typer.Option(True, "--dry-run/--apply", help="Preview vs apply. Default: dry-run."),
):
    """Find unused symbols (dead code) and offer to remove them.

    Scans the workspace index for symbols that have **zero dependents**
    (no other file imports them).  Generates a ProposedPlan to remove
    unused imports and functions.
    """
    from code4u.cli.health import run_health_check

    resolved = _resolve_path(path)
    if not Path(resolved).is_dir():
        _print_error(f"Not a directory: {resolved}")
        raise typer.Exit(1)

    apply = fix or not dry_run
    run_health_check(resolved, apply=apply, console=console)


# ---------------------------------------------------------------------------
# code4u cycles
# ---------------------------------------------------------------------------

@app.command()
def cycles(
    path: str = typer.Argument(".", help="Workspace root to scan."),
):
    """Detect circular import chains in the workspace."""
    from code4u.code_intelligence.knowledge_graph.symbol_indexer import SymbolIndexer

    resolved = _resolve_path(path)
    if not Path(resolved).is_dir():
        _print_error(f"Not a directory: {resolved}")
        raise typer.Exit(1)

    indexer = SymbolIndexer()
    with console.status("[cyan]Indexing...[/cyan]"):
        dep_map = indexer.index_workspace(resolved)

    detected = dep_map.detect_cycles()

    if not detected:
        console.print("[bold green]No circular dependencies found.[/bold green]")
        return

    console.print(
        f"[bold yellow]Found {len(detected)} circular import chain(s):[/bold yellow]"
    )
    for i, cycle in enumerate(detected, 1):
        chain = " -> ".join(
            "/".join(Path(f).parts[-2:]) for f in cycle
        )
        console.print(f"  {i}. {chain}")


# ---------------------------------------------------------------------------
# code4u history
# ---------------------------------------------------------------------------

@app.command()
def history(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of records to show."),
    stats: bool = typer.Option(False, "--stats", "-s", help="Show aggregate statistics."),
):
    """View refactor job history and success/failure rates."""
    from code4u.cli.history import read_history, summary_stats
    from datetime import datetime

    if stats:
        s = summary_stats()
        if s["total_jobs"] == 0:
            console.print("[dim]No history yet. Run a refactor to start tracking.[/dim]")
            return

        stat_table = Table(title="Refactor Analytics", border_style="cyan")
        stat_table.add_column("Metric", style="white")
        stat_table.add_column("Value", style="bold cyan", justify="right")
        stat_table.add_row("Total jobs", str(s["total_jobs"]))
        stat_table.add_row("Successful", f"[green]{s['success']}[/green]")
        stat_table.add_row("Failed", f"[red]{s['failed']}[/red]")
        stat_table.add_row("Dry runs", str(s["dry_runs"]))
        stat_table.add_row("Success rate", f"{s['success_rate']}%")
        stat_table.add_row("Avg duration", f"{s['avg_duration_ms']:.0f} ms")
        console.print(stat_table)

        if s.get("by_intent_type"):
            type_table = Table(title="By Intent Type", border_style="cyan")
            type_table.add_column("Type", style="white")
            type_table.add_column("Total", justify="right")
            type_table.add_column("OK", style="green", justify="right")
            type_table.add_column("Fail", style="red", justify="right")
            for it, counts in s["by_intent_type"].items():
                type_table.add_row(
                    it, str(counts["total"]),
                    str(counts["success"]), str(counts["failed"]),
                )
            console.print(type_table)
        return

    records = read_history(limit=limit)
    if not records:
        console.print("[dim]No history yet. Run a refactor to start tracking.[/dim]")
        return

    table = Table(title=f"Last {len(records)} Jobs", border_style="cyan")
    table.add_column("Time", style="dim")
    table.add_column("Intent", style="white", max_width=40)
    table.add_column("Type", style="cyan")
    table.add_column("Files", justify="right")
    table.add_column("Duration", justify="right")
    table.add_column("Outcome")

    for r in records:
        ts = datetime.fromtimestamp(r.get("ts", 0)).strftime("%m-%d %H:%M")
        outcome = r.get("outcome", "?")
        outcome_styled = (
            f"[green]{outcome}[/green]" if outcome == "APPLIED"
            else f"[red]{outcome}[/red]"
        )
        if r.get("dry_run"):
            outcome_styled += " [dim](dry)[/dim]"
        table.add_row(
            ts,
            (r.get("intent", "")[:40]),
            r.get("intent_type", "?"),
            str(r.get("file_count", "?")),
            f"{r.get('duration_ms', 0):.0f}ms",
            outcome_styled,
        )

    console.print(table)


# ---------------------------------------------------------------------------
# code4u visual
# ---------------------------------------------------------------------------

@app.command()
def visual(
    image: str = typer.Argument(..., help="Path to an image file (PNG/JPEG/WebP)."),
    intent: str = typer.Option("", "--intent", "-i", help="Refactor intent."),
    workspace: str = typer.Option(".", "--workspace", "-w", help="Workspace root."),
    ground_only: bool = typer.Option(False, "--ground-only", help="Only show grounding (no refactor)."),
):
    """Upload an image and map visual elements to codebase symbols.

    Uses the Vision LLM (or local keyword matching) to identify
    which files and symbols correspond to the visual elements
    in the provided image.
    """
    import base64
    from code4u.ai_engine.llm.visual_grounder import VisualGrounder
    from code4u.code_intelligence.knowledge_graph.symbol_indexer import SymbolIndexer

    img_path = Path(image)
    if not img_path.is_file():
        _print_error(f"Image not found: {image}")
        raise typer.Exit(1)

    suffix = img_path.suffix.lower()
    media_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    media_type = media_map.get(suffix, "image/png")

    resolved = _resolve_path(workspace)
    if not Path(resolved).is_dir():
        _print_error(f"Not a directory: {resolved}")
        raise typer.Exit(1)

    image_b64 = base64.b64encode(img_path.read_bytes()).decode("utf-8")

    with console.status("[cyan]Indexing workspace...[/cyan]"):
        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace(resolved)

    console.print(
        f"[dim]Indexed {dep_map.stats['indexed_files']} files "
        f"({dep_map.stats['total_symbols']} symbols)[/dim]\n"
    )

    async def _ground():
        grounder = VisualGrounder(dep_map=dep_map)
        return await grounder.ground(
            image_base64=image_b64,
            intent=intent or "Identify visual elements",
            media_type=media_type,
        )

    with console.status("[cyan]Running visual grounding...[/cyan]"):
        result = _run_async(_ground())

    console.print(Panel(
        result.visual_summary or "No summary available.",
        title="Visual Summary",
        border_style="cyan",
    ))

    if result.matched_files:
        file_table = Table(title="Matched Files", border_style="green")
        file_table.add_column("#", style="dim", justify="right")
        file_table.add_column("File", style="white")

        for i, f in enumerate(result.matched_files, 1):
            short = "/".join(Path(f).parts[-3:])
            file_table.add_row(str(i), short)
        console.print(file_table)

    if result.matched_symbols:
        sym_table = Table(title="Matched Symbols", border_style="green")
        sym_table.add_column("Symbol", style="bold")
        sym_table.add_column("File", style="white")
        sym_table.add_column("Kind", style="cyan")
        sym_table.add_column("Confidence", justify="right")
        sym_table.add_column("Visual Role", style="dim")

        for s in result.matched_symbols:
            short = "/".join(Path(s.file_path).parts[-3:])
            conf_style = "green" if s.confidence >= 0.7 else "yellow" if s.confidence >= 0.5 else "red"
            sym_table.add_row(
                s.name, short, s.kind,
                f"[{conf_style}]{s.confidence:.0%}[/{conf_style}]",
                s.visual_role[:50],
            )
        console.print(sym_table)

    if result.is_ui_layout:
        console.print("[bold cyan]This appears to be a UI Layout change.[/bold cyan]")

    if result.suggested_intent and result.suggested_intent != intent:
        console.print(f"[dim]Suggested intent: {result.suggested_intent}[/dim]")

    if not ground_only and intent and result.matched_files:
        console.print("\n[bold]Running refactor pipeline on matched files...[/bold]")
        primary = result.matched_files[0]
        effective_intent = f"[UI Layout] {intent}" if result.is_ui_layout else intent
        _run_refactor_pipeline(
            intent=effective_intent,
            file_path=primary,
            workspace_path=workspace,
            dry_run=True,
        )


# ---------------------------------------------------------------------------
# code4u predict
# ---------------------------------------------------------------------------

@app.command()
def predict(
    symbol: str = typer.Argument(..., help="Symbol name to analyze."),
    workspace: str = typer.Option(".", "--workspace", "-w", help="Workspace root."),
    max_depth: int = typer.Option(5, "--depth", help="Max recursion depth for transitive dependents."),
):
    """Predict the blast radius of modifying or deleting a symbol.

    Shows every file that directly or transitively depends on the
    given symbol — answering "What breaks if I change this?"
    """
    from code4u.code_intelligence.knowledge_graph.symbol_indexer import SymbolIndexer

    resolved = _resolve_path(workspace)
    if not Path(resolved).is_dir():
        _print_error(f"Not a directory: {resolved}")
        raise typer.Exit(1)

    with console.status("[cyan]Indexing...[/cyan]"):
        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace(resolved)

    defs = dep_map.get_symbol_defs(symbol)
    if not defs:
        _print_error(f"Symbol '{symbol}' not found in workspace index.")
        raise typer.Exit(1)

    defining_file = defs[0].file_path
    direct = dep_map.get_dependents(symbol)

    try:
        transitive = dep_map.get_transitive_dependents(
            symbol, defining_file, max_depth=max_depth
        )
    except Exception:
        transitive = set(direct)

    console.print(f"\n[bold]Symbol:[/bold]  {symbol}")
    console.print(f"[bold]Defined:[/bold] {'/'.join(Path(defining_file).parts[-3:])}")
    console.print(f"[bold]Kind:[/bold]    {defs[0].kind}")

    severity = (
        "[green]low[/green]" if len(transitive) <= 2
        else "[yellow]medium[/yellow]" if len(transitive) <= 5
        else "[red]high[/red]" if len(transitive) <= 10
        else "[bold red]critical[/bold red]"
    )
    console.print(f"[bold]Blast Radius:[/bold] {len(transitive)} file(s) — {severity}\n")

    if direct:
        table = Table(title="Direct Dependents", border_style="cyan")
        table.add_column("#", style="dim", justify="right")
        table.add_column("File", style="white")
        for i, f in enumerate(sorted(direct), 1):
            short = "/".join(Path(f).parts[-3:])
            table.add_row(str(i), short)
        console.print(table)

    transitive_only = transitive - set(direct) - {defining_file}
    if transitive_only:
        console.print()
        trans_table = Table(title="Transitive Dependents", border_style="yellow")
        trans_table.add_column("#", style="dim", justify="right")
        trans_table.add_column("File", style="white")
        for i, f in enumerate(sorted(transitive_only), 1):
            short = "/".join(Path(f).parts[-3:])
            trans_table.add_row(str(i), short)
        console.print(trans_table)

    if not direct:
        console.print("[green]No dependents found — safe to modify.[/green]")


# ---------------------------------------------------------------------------
# code4u sessions
# ---------------------------------------------------------------------------

@app.command()
def sessions(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of sessions to show."),
):
    """List recent refactoring sessions."""
    from code4u.platform_core.agents.session_manager import SessionManager

    mgr = SessionManager()
    session_list = mgr.list_sessions(limit=limit)

    if not session_list:
        console.print("[dim]No sessions yet. Use 'code4u refactor' with --session to start one.[/dim]")
        return

    from datetime import datetime

    table = Table(title=f"Recent Sessions ({len(session_list)})", border_style="cyan")
    table.add_column("Session ID", style="dim", max_width=12)
    table.add_column("Workspace", style="white")
    table.add_column("Jobs", justify="right")
    table.add_column("Last Intent", max_width=40)
    table.add_column("Updated", style="dim")

    for s in session_list:
        short_id = s.session_id[:8] + "..."
        ws = "/".join(Path(s.workspace_path).parts[-2:])
        last_intent = s.last_job.intent[:40] if s.last_job else "-"
        updated = datetime.fromtimestamp(s.updated_at).strftime("%m-%d %H:%M") if s.updated_at else "-"
        table.add_row(short_id, ws, str(s.job_count), last_intent, updated)

    console.print(table)


# ---------------------------------------------------------------------------
# code4u recipes
# ---------------------------------------------------------------------------

@app.command()
def recipes(
    workspace: str = typer.Option(".", "--workspace", "-w", help="Workspace root."),
    tag: Optional[str] = typer.Option(None, "--tag", "-t", help="Filter by tag."),
):
    """List available refactoring recipes (global + project-local)."""
    from code4u.core.recipes import RecipeRegistry

    resolved = _resolve_path(workspace)
    registry = RecipeRegistry(workspace_path=resolved)
    registry.load()

    recipe_list = registry.list_by_tag(tag) if tag else registry.list_recipes()

    if not recipe_list:
        console.print("[dim]No recipes found.[/dim]")
        console.print(
            "[dim]Place YAML files in ~/.code4u/recipes/ or .code4u/recipes/[/dim]"
        )
        return

    table = Table(title=f"Recipes ({len(recipe_list)})", border_style="cyan")
    table.add_column("ID", style="bold cyan")
    table.add_column("Name", style="white")
    table.add_column("Selector", style="dim")
    table.add_column("Tags", style="dim")
    table.add_column("Source", style="dim")

    for r in recipe_list:
        source = "project" if r.is_project_local else "global"
        tags = ", ".join(r.tags[:3]) if r.tags else "-"
        table.add_row(r.id, r.name, r.selector.file_glob, tags, source)

    console.print(table)


# ---------------------------------------------------------------------------
# code4u run-recipe
# ---------------------------------------------------------------------------

@app.command("run-recipe")
def run_recipe(
    recipe_id: str = typer.Argument(..., help="ID of the recipe to run."),
    workspace: str = typer.Option(".", "--workspace", "-w", help="Workspace root."),
    dry_run: bool = typer.Option(True, "--dry-run/--apply", help="Preview vs apply. Default: dry-run."),
    extra: str = typer.Option("", "--extra", "-e", help="Additional context for the prompt."),
):
    """Run a specific recipe through the refactoring pipeline.

    The recipe's file selector is applied to the workspace index, and
    the prompt template is used as the refactoring intent.  Full Atomic
    Rollback and validation are active.
    """
    from code4u.core.recipes import RecipeRegistry
    from code4u.code_intelligence.knowledge_graph.symbol_indexer import SymbolIndexer

    resolved = _resolve_path(workspace)
    if not Path(resolved).is_dir():
        _print_error(f"Not a directory: {resolved}")
        raise typer.Exit(1)

    registry = RecipeRegistry(workspace_path=resolved)
    registry.load()

    recipe = registry.get(recipe_id)
    if not recipe:
        _print_error(f"Recipe not found: {recipe_id}")
        console.print(f"[dim]Available: {', '.join(r.id for r in registry.list_recipes()) or '(none)'}[/dim]")
        raise typer.Exit(1)

    console.print(Panel(
        f"[bold]{recipe.name}[/bold]\n{recipe.description}",
        title=f"Recipe: {recipe.id}",
        border_style="cyan",
    ))

    with console.status("[cyan]Indexing workspace...[/cyan]"):
        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace(resolved)

    all_files = list(dep_map._file_symbols.keys())
    matched = recipe.selector.filter_files(all_files)

    console.print(
        f"[dim]Selector '[bold]{recipe.selector.file_glob}[/bold]' matched "
        f"{len(matched)} / {len(all_files)} files[/dim]"
    )

    if not matched:
        console.print("[yellow]No files matched the recipe selector.[/yellow]")
        raise typer.Exit(0)

    file_table = Table(title="Matched Files", border_style="green")
    file_table.add_column("#", style="dim", justify="right")
    file_table.add_column("File", style="white")
    for i, f in enumerate(sorted(matched)[:20], 1):
        short = "/".join(Path(f).parts[-3:])
        file_table.add_row(str(i), short)
    if len(matched) > 20:
        file_table.add_row("...", f"({len(matched) - 20} more)")
    console.print(file_table)

    intent = recipe.build_intent(extra)
    primary_file = matched[0]

    console.print(f"\n[bold]Intent:[/bold] {intent[:200]}{'...' if len(intent) > 200 else ''}")
    if dry_run:
        console.print("[bold yellow]Mode:[/bold yellow] DRY RUN (no disk writes)\n")

    _run_refactor_pipeline(
        intent=intent,
        file_path=primary_file,
        workspace_path=workspace,
        dry_run=dry_run,
    )


# ---------------------------------------------------------------------------
# code4u standardize
# ---------------------------------------------------------------------------

@app.command()
def standardize(
    workspace: str = typer.Option(".", "--workspace", "-w", help="Workspace root."),
    dry_run: bool = typer.Option(True, "--dry-run/--apply", help="Preview vs apply."),
    tag: str = typer.Option("", "--tag", "-t", help="Only run recipes with this tag."),
):
    """Run all available recipes as a standards sweep.

    Executes every loaded recipe (or those matching ``--tag``) against
    the workspace, applying each recipe's selector to filter files.
    This is the team's "Golden Path" enforcement tool.
    """
    from code4u.core.recipes import RecipeRegistry
    from code4u.code_intelligence.knowledge_graph.symbol_indexer import SymbolIndexer

    resolved = _resolve_path(workspace)
    if not Path(resolved).is_dir():
        _print_error(f"Not a directory: {resolved}")
        raise typer.Exit(1)

    registry = RecipeRegistry(workspace_path=resolved)
    registry.load()

    recipe_list = registry.list_by_tag(tag) if tag else registry.list_recipes()

    if not recipe_list:
        console.print("[dim]No recipes found — nothing to standardize.[/dim]")
        raise typer.Exit(0)

    console.print(
        f"[bold]Standardize:[/bold] running {len(recipe_list)} recipe(s) "
        f"{'(dry-run)' if dry_run else '(apply)'}\n"
    )

    with console.status("[cyan]Indexing workspace...[/cyan]"):
        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace(resolved)

    all_files = list(dep_map._file_symbols.keys())

    for idx, recipe in enumerate(recipe_list, 1):
        matched = recipe.selector.filter_files(all_files)
        console.print(
            f"[bold cyan]({idx}/{len(recipe_list)})[/bold cyan] "
            f"[bold]{recipe.name}[/bold] — {len(matched)} files match"
        )

        if not matched:
            console.print("  [dim]Skipped (no matching files)[/dim]")
            continue

        intent = recipe.build_intent()
        try:
            _run_refactor_pipeline(
                intent=intent,
                file_path=matched[0],
                workspace_path=workspace,
                dry_run=dry_run,
            )
        except (typer.Exit, SystemExit):
            console.print(f"  [yellow]Recipe '{recipe.id}' did not complete.[/yellow]")
        except Exception as exc:
            console.print(f"  [red]Recipe '{recipe.id}' failed: {exc}[/red]")

    _print_success(f"Standardization complete — {len(recipe_list)} recipe(s) processed.")


# ---------------------------------------------------------------------------
# code4u agents
# ---------------------------------------------------------------------------

@app.command("agents")
def list_agents(
    workspace: str = typer.Option(".", "--workspace", "-w", help="Workspace root."),
):
    """List all available agents (built-in + plugins)."""
    from code4u.agents.orchestrator.models import AgentType
    from code4u.core.loader import PluginLoader

    table = Table(title="Available Agents", show_header=True, header_style="bold cyan")
    table.add_column("Icon", width=4)
    table.add_column("Name", style="bold")
    table.add_column("Type", style="cyan")
    table.add_column("Source", style="dim")
    table.add_column("Description")

    built_in = [
        ("📇", "index", "index", "built-in", "Index workspace symbols"),
        ("👁 ", "vision", "vision", "built-in", "Analyze UI screenshots"),
        ("🔗", "graph", "graph", "built-in", "Code architecture analysis"),
        ("📦", "migration", "migration", "built-in", "Multi-file code migration"),
        ("🩹", "heal", "heal", "built-in", "Diagnose and fix errors"),
        ("⚖️ ", "jury", "jury", "built-in", "Quality review and guardrails"),
        ("📋", "recipe", "recipe", "built-in", "Apply code recipes"),
        ("🔧", "refactor", "refactor", "built-in", "General refactoring"),
        ("💬", "chat", "chat", "built-in", "Architectural conversations"),
    ]
    for icon, name, atype, source, desc in built_in:
        table.add_row(icon, name, atype, source, desc)

    # Discover plugins
    ws_path = str(Path(workspace).resolve())
    loader = PluginLoader(workspace_path=ws_path)
    plugins = loader.discover()

    for agent in plugins:
        table.add_row(
            agent.manifest.icon,
            agent.manifest.name,
            agent.manifest.agent_type.value,
            "[green]plugin[/green]",
            agent.manifest.description[:50],
        )

    console.print(table)
    if plugins:
        console.print(f"\n[green]✓[/green] {len(plugins)} plugin(s) discovered.")
    if loader.errors:
        console.print(f"[yellow]⚠[/yellow] {len(loader.errors)} plugin(s) failed to load.")


# ---------------------------------------------------------------------------
# code4u forge
# ---------------------------------------------------------------------------

@app.command()
def forge(
    sample: str = typer.Argument(..., help="Path to the code sample to analyze."),
    output: str = typer.Option("", "--output", "-o", help="Output path for the recipe YAML."),
    save: bool = typer.Option(False, "--save", help="Save to ~/.code4u/recipes/."),
):
    """Forge a new Recipe by analyzing a code sample.

    Analyzes patterns (imports, decorators, naming, structure) in the
    given file and generates a YAML recipe to replicate that style.
    """
    from code4u.agents.meta.forge import ForgeAgent

    sample_path = str(Path(sample).resolve())
    if not Path(sample_path).is_file():
        _print_error(f"File not found: {sample_path}")
        raise typer.Exit(1)

    forge_agent = ForgeAgent()
    result = forge_agent.forge_from_file(sample_path)

    # Show detected patterns
    table = Table(title="Detected Patterns", show_header=True, header_style="bold cyan")
    table.add_column("Type", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Description")
    table.add_column("#", justify="right")

    for p in result.patterns:
        table.add_row(p.pattern_type, p.name, p.description[:60], str(p.frequency))
    console.print(table)

    # Show recipe YAML
    console.print(Panel(result.recipe_yaml, title="[bold green]Forged Recipe[/bold green]", border_style="green"))

    # Save if requested
    if save or output:
        if output:
            out_path = output
        else:
            out_path = str(Path.home() / ".code4u" / "recipes" / f"{result.id}.yaml")
        saved = result.save(out_path)
        _print_success(f"Recipe saved to {saved}")
    else:
        console.print("[dim]Use --save to persist this recipe, or --output PATH to save to a specific file.[/dim]")


# ---------------------------------------------------------------------------
# code4u install
# ---------------------------------------------------------------------------

@app.command("install")
def install_pack(
    source: str = typer.Argument(..., help="Path to manifest.json or recipe YAML file."),
):
    """Install a recipe pack or individual recipe from a manifest file."""
    import json as json_mod

    source_path = Path(source).resolve()
    if not source_path.is_file():
        _print_error(f"File not found: {source_path}")
        raise typer.Exit(1)

    if source_path.suffix == ".json":
        data = json_mod.loads(source_path.read_text(encoding="utf-8"))

        from code4u.core.loader import PluginLoader
        loader = PluginLoader()
        result = loader.install_from_manifest(data)

        if not result.get("valid"):
            _print_error(f"Invalid manifest: {result.get('error', 'unknown')}")
            raise typer.Exit(1)

        console.print(Panel(
            f"[bold]{result['name']}[/bold] v{result['version']}\n"
            f"Author: {result.get('author', 'unknown')}\n"
            f"Recipes installed: {result.get('installedRecipes', 0)}",
            title="[bold green]Package Installed[/bold green]",
            border_style="green",
        ))

    elif source_path.suffix in (".yaml", ".yml"):
        from code4u.core.recipes import Recipe, RecipeRegistry

        recipe = Recipe.from_yaml(str(source_path))
        registry = RecipeRegistry()
        registry.register(recipe)

        console.print(Panel(
            f"Recipe [bold]{recipe.id}[/bold] installed.\n"
            f"Name: {recipe.name}\n"
            f"Selector: {recipe.selector.file_glob if recipe.selector else '*'}",
            title="[bold green]Recipe Installed[/bold green]",
            border_style="green",
        ))

    else:
        _print_error(f"Unsupported file type: {source_path.suffix}. Use .json or .yaml.")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# code4u dashboard
# ---------------------------------------------------------------------------

@app.command()
def dashboard(
    workspace: str = typer.Argument(
        ".", help="Root directory of the workspace to monitor."
    ),
    refresh: float = typer.Option(1.0, "--refresh", "-r", help="Refresh rate in seconds."),
):
    """Launch the War Room TUI dashboard.

    A full-screen real-time dashboard showing sessions, swarm DAG,
    dependency graph stats, and ROI analytics.
    """
    from code4u.interfaces.cli.dashboard import WarRoomDashboard

    ws_path = str(Path(workspace).resolve())
    console.print(Panel(
        f"[bold green]Launching War Room Dashboard[/bold green]\n"
        f"Workspace: {ws_path}\n"
        f"Refresh: {refresh}s\n"
        f"Press Ctrl+C to exit.",
        title="⚡ code4u.ai",
        border_style="blue",
    ))

    dash = WarRoomDashboard(workspace=ws_path, refresh_rate=refresh)
    dash.run()


# ---------------------------------------------------------------------------
# code4u analyze --nexus
# ---------------------------------------------------------------------------

@app.command("analyze")
def analyze_nexus(
    workspace: str = typer.Argument(".", help="Root directory containing repos."),
    nexus: bool = typer.Option(False, "--nexus", help="Enable multi-repo Nexus analysis."),
    symbol: str = typer.Option("", "--symbol", "-s", help="Symbol to check blast radius for."),
):
    """Analyze codebase — with --nexus for cross-repo impact."""
    from code4u.core.nexus import NexusContext
    from code4u.agents.nexus.impact_analyzer import ImpactAnalyzer

    ws_path = str(Path(workspace).resolve())

    if not nexus:
        console.print("[yellow]Use --nexus to enable multi-repo analysis.[/yellow]")
        raise typer.Exit()

    with console.status("[bold blue]Scanning for repositories..."):
        ctx = NexusContext(ws_path)
        repos = ctx.scan()
    _print_success(f"Found {len(repos)} repositories")

    table = Table(title="Discovered Repos", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="bold")
    table.add_column("Markers", style="dim")
    table.add_column("Path")
    for r in repos:
        table.add_row(r.name, ", ".join(r.markers), r.path)
    console.print(table)

    with console.status("[bold blue]Indexing all repos..."):
        ctx.index_all()

    with console.status("[bold blue]Linking cross-repo dependencies..."):
        edges = ctx.link_repos()
    _print_success(f"Discovered {len(edges)} cross-repo edges")

    summary = ctx.summary()
    stats = Table(title="Nexus Summary", show_header=True, header_style="bold green")
    stats.add_column("Metric", style="bold")
    stats.add_column("Value", justify="right", style="cyan")
    stats.add_row("Total Repos", str(summary["repoCount"]))
    stats.add_row("Total Files", str(summary["totalFiles"]))
    stats.add_row("Total Symbols", str(summary["totalSymbols"]))
    stats.add_row("Cross-Repo Edges", str(summary["crossRepoEdges"]))
    console.print(stats)

    if symbol:
        analyzer = ImpactAnalyzer(ctx.registry)
        blast = analyzer.analyze(symbol)
        console.print(Panel(
            f"[bold]Symbol:[/bold] {blast.symbol_name}\n"
            f"[bold]Origin:[/bold] {blast.origin_repo} ({blast.origin_file})\n"
            f"[bold]Severity:[/bold] {blast.severity}\n"
            f"[bold]Affected Repos:[/bold] {blast.total_repos}\n"
            f"[bold]Affected Files:[/bold] {blast.total_files}",
            title="[bold red]Blast Radius[/bold red]",
            border_style="red",
        ))
        for repo in blast.affected_repos:
            console.print(f"  [yellow]{repo.name}[/yellow] ({repo.file_count} files, severity={repo.severity})")
            for f in repo.files:
                console.print(f"    - {f.path}")
        if blast.pr_plan:
            console.print("\n[bold]Multi-PR Plan:[/bold]")
            for pr in blast.pr_plan:
                console.print(f"  [{pr['priority']}] {pr['repo']}: {pr['title']} ({pr['fileCount']} files)")
    elif edges:
        analyzer = ImpactAnalyzer(ctx.registry)
        high_risk = analyzer.high_risk_symbols(min_repos=1)
        if high_risk:
            risk_table = Table(title="High-Risk Symbols", show_header=True, header_style="bold red")
            risk_table.add_column("Symbol", style="bold")
            risk_table.add_column("Origin", style="cyan")
            risk_table.add_column("Repos", justify="right")
            risk_table.add_column("Files", justify="right")
            risk_table.add_column("Severity", style="red")
            for b in high_risk[:10]:
                risk_table.add_row(b.symbol_name, b.origin_repo, str(b.total_repos), str(b.total_files), b.severity)
            console.print(risk_table)


# ---------------------------------------------------------------------------
# code4u welcome
# ---------------------------------------------------------------------------

@app.command()
def welcome(
    workspace: str = typer.Argument(".", help="Workspace to diagnose."),
):
    """Run the onboarding diagnostic and show system status."""
    from code4u.core.version import VERSION, VersionManager

    vm = VersionManager()
    ws_path = str(Path(workspace).resolve())

    # Banner
    console.print(Panel(
        f"[bold cyan]⚡ code4u.ai v{VERSION}[/bold cyan]\n"
        f"[dim]AI-Native Engineering Platform[/dim]",
        border_style="cyan",
    ))

    # Ensure directories
    with console.status("[bold blue]Setting up directories..."):
        dirs = vm.ensure_directories()
    _print_success(f"Directory structure ready ({len(dirs)} directories)")

    # Install base recipes
    with console.status("[bold blue]Checking recipes..."):
        installed = vm.install_base_recipes()
    if installed:
        _print_success(f"Installed {installed} base recipes")
    else:
        console.print("  [dim]Base recipes already installed[/dim]")

    # Run diagnostics
    with console.status("[bold blue]Running diagnostics..."):
        diag = vm.run_diagnostics(ws_path)

    # Diagnostic table
    table = Table(title="System Diagnostic", show_header=True, header_style="bold green")
    table.add_column("Check", style="bold")
    table.add_column("Status", justify="right")

    table.add_row("Version", f"[cyan]{diag['version']}[/cyan]")
    table.add_row("Config Dir", "[green]✓[/green]" if diag["code4u_dir_exists"] else "[red]✗[/red]")
    table.add_row("Plugins", str(diag.get("plugins_count", 0)))
    table.add_row("Recipes", str(diag.get("recipes_count", 0)))
    table.add_row("Rules", str(diag.get("rules_count", 0)))

    if diag.get("workspace_exists"):
        table.add_row("Workspace", f"[green]✓[/green] {ws_path}")
        table.add_row("Python Files", str(diag.get("python_files", 0)))
        repo_count = diag.get("repo_count", 0)
        if repo_count:
            table.add_row("Git Repos", f"[cyan]{repo_count}[/cyan]")
            for repo in diag.get("repos", [])[:5]:
                table.add_row(f"  └ {repo}", "[dim]discovered[/dim]")
    console.print(table)

    # Available agents
    agents_table = Table(title="Available Agents", show_header=True, header_style="bold cyan")
    agents_table.add_column("Icon", width=4)
    agents_table.add_column("Agent", style="bold")
    agents_table.add_column("Purpose")

    built_in = [
        ("📇", "Index", "Index workspace symbols"),
        ("🔧", "Refactor", "General refactoring"),
        ("👁 ", "Vision", "Analyze UI screenshots"),
        ("🔗", "Graph", "Code architecture analysis"),
        ("📦", "Migration", "Multi-file code migration"),
        ("🩹", "Heal", "Diagnose and fix errors"),
        ("⚖️ ", "Jury", "Quality review and guardrails"),
        ("📋", "Recipe", "Apply code recipes"),
        ("💬", "Chat", "Architectural conversations"),
        ("⚡", "Profiler", "Performance optimization"),
    ]
    for icon, name, purpose in built_in:
        agents_table.add_row(icon, name, purpose)

    # Discover plugins
    try:
        from code4u.core.loader import PluginLoader
        loader = PluginLoader(workspace_path=ws_path)
        plugins = loader.discover()
        for agent in plugins:
            agents_table.add_row(
                agent.manifest.icon, agent.manifest.name,
                f"[green](plugin)[/green] {agent.manifest.description[:40]}",
            )
    except Exception:
        pass

    console.print(agents_table)

    # ROI ticker
    try:
        from code4u.models.analytics import AuditStore
        store = AuditStore()
        summary = store.summary()
        total_sug = summary.get("totalSuggestions", 0)
        accepted = summary.get("totalAccepted", 0)
        minutes = summary.get("totalMinutesSaved", 0)
        if total_sug > 0:
            console.print(Panel(
                f"[bold green]✨ code4u has saved {minutes / 60:.1f} hours[/bold green] "
                f"across {accepted}/{total_sug} accepted suggestions.",
                border_style="green",
            ))
    except Exception:
        pass

    # Quick start
    console.print(Panel(
        "[bold]Quick Start:[/bold]\n"
        f"  [cyan]code4u index {workspace}[/cyan]       Index this workspace\n"
        f"  [cyan]code4u health {workspace}[/cyan]      Find unused code\n"
        "  [cyan]code4u dashboard .[/cyan]       Launch the War Room\n"
        "  [cyan]code4u recipes list[/cyan]      See available recipes\n"
        "  [cyan]code4u --help[/cyan]            Full command reference",
        title="[bold green]Ready to go![/bold green]",
        border_style="green",
    ))


# ---------------------------------------------------------------------------
# code4u update
# ---------------------------------------------------------------------------

@app.command()
def update():
    """Check for updates and install the latest version."""
    from code4u.core.version import VERSION, VersionManager

    vm = VersionManager()
    console.print(f"[dim]Current version: v{VERSION}[/dim]")

    with console.status("[bold blue]Checking for updates..."):
        info = vm.check_update()

    if info.error:
        console.print(f"[yellow]Could not check for updates: {info.error}[/yellow]")
        console.print("[dim]You can update manually: pip install --upgrade code4u-backend[/dim]")
        return

    if info.update_available:
        console.print(Panel(
            f"[bold green]Update available![/bold green]\n"
            f"  Current: v{info.local_version}\n"
            f"  Latest:  v{info.remote_version}\n"
            f"{info.release_notes}" if info.release_notes else "",
            title="[bold cyan]code4u update[/bold cyan]",
            border_style="cyan",
        ))
        console.print("[dim]Run: pip install --upgrade code4u-backend[/dim]")
    else:
        _print_success(f"You are on the latest version (v{VERSION})")


# ---------------------------------------------------------------------------
# code4u --version
# ---------------------------------------------------------------------------

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Show version."),
):
    """code4u.ai — AI-native refactoring from your terminal."""
    if version:
        from code4u.core.version import VERSION
        console.print(f"code4u v{VERSION}")
        raise typer.Exit()


if __name__ == "__main__":
    app()
