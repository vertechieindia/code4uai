"""War Room Dashboard — rich-powered TUI for code4u.ai.

A high-information-density terminal dashboard with 3 columns:
  - **Left sidebar**: Active sessions, recent audit events, file watcher log.
  - **Center pane**: Swarm DAG visualizer + command bar.
  - **Right pane**: Dependency graph stats, hot files, noisy recipes.
  - **Footer**: ROI ticker ("14.5 Hours Saved This Week").

The dashboard uses ``rich.live.Live`` for real-time updates and
polls backend state periodically (or receives push events via
a WebSocket client).

Usage::

    from code4u.interfaces.cli.dashboard import WarRoomDashboard
    dashboard = WarRoomDashboard(workspace="/path/to/project")
    dashboard.run()  # blocking — takes over the terminal
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

import structlog

logger = structlog.get_logger("dashboard")


# ---------------------------------------------------------------------------
# Data models for dashboard state
# ---------------------------------------------------------------------------

@dataclass
class SessionInfo:
    """One active session shown in the sidebar."""
    session_id: str
    display_name: str = ""
    workspace: str = ""
    active_files: List[str] = field(default_factory=list)
    active_intent: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sessionId": self.session_id,
            "displayName": self.display_name,
            "workspace": self.workspace,
            "activeFiles": self.active_files,
            "activeIntent": self.active_intent,
        }


@dataclass
class FileEvent:
    """A file change detected by the watcher."""
    file_path: str
    event_type: str = "modified"  # created, modified, deleted
    timestamp: float = field(default_factory=time.time)

    def age_str(self) -> str:
        ago = time.time() - self.timestamp
        if ago < 60:
            return f"{int(ago)}s ago"
        return f"{int(ago / 60)}m ago"


@dataclass
class SwarmTaskView:
    """One task in the swarm DAG for rendering."""
    task_id: str
    agent_type: str
    description: str
    status: str = "pending"
    duration_ms: float = 0.0
    error: str = ""
    dependencies: List[str] = field(default_factory=list)


@dataclass
class SwarmView:
    """Current swarm state for rendering."""
    graph_id: str = ""
    goal: str = ""
    tasks: List[SwarmTaskView] = field(default_factory=list)
    progress: float = 0.0
    is_complete: bool = False
    is_success: bool = False
    events: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class GraphStats:
    """Dependency graph statistics for the right panel."""
    total_files: int = 0
    total_symbols: int = 0
    total_imports: int = 0
    cycles: int = 0
    hot_files: List[str] = field(default_factory=list)
    noisy_recipes: List[Dict[str, Any]] = field(default_factory=list)
    perf_hotspots: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ROIData:
    """ROI analytics for the footer ticker."""
    total_suggestions: int = 0
    accepted_count: int = 0
    minutes_saved: float = 0.0
    hours_saved: float = 0.0
    repos_count: int = 0
    reviews_count: int = 0


@dataclass
class NexusView:
    """Multi-repo Nexus data for the dashboard."""
    repo_count: int = 0
    total_files: int = 0
    total_symbols: int = 0
    cross_edges: int = 0
    repos: List[Dict[str, Any]] = field(default_factory=list)
    high_risk: List[Dict[str, Any]] = field(default_factory=list)
    enabled: bool = False


@dataclass
class DriftWarning:
    """A drift violation shown in the TUI sidebar."""
    rule_id: str
    rule_name: str
    severity: str
    file_path: str
    message: str
    timestamp: float = field(default_factory=time.time)

    def age_str(self) -> str:
        ago = time.time() - self.timestamp
        if ago < 60:
            return f"{int(ago)}s ago"
        return f"{int(ago / 60)}m ago"


@dataclass
class DashboardState:
    """Complete snapshot of dashboard state."""
    sessions: List[SessionInfo] = field(default_factory=list)
    file_events: List[FileEvent] = field(default_factory=list)
    swarm: SwarmView = field(default_factory=SwarmView)
    graph_stats: GraphStats = field(default_factory=GraphStats)
    roi: ROIData = field(default_factory=ROIData)
    nexus: NexusView = field(default_factory=NexusView)
    drift_warnings: List[DriftWarning] = field(default_factory=list)
    command_history: List[str] = field(default_factory=list)
    pending_plan: Optional[Dict[str, Any]] = None
    status_message: str = "Ready"
    workspace: str = ""

    def add_file_event(self, event: FileEvent) -> None:
        self.file_events.insert(0, event)
        if len(self.file_events) > 20:
            self.file_events = self.file_events[:20]

    def add_drift_warning(self, warning: DriftWarning) -> None:
        self.drift_warnings.insert(0, warning)
        if len(self.drift_warnings) > 15:
            self.drift_warnings = self.drift_warnings[:15]


# ---------------------------------------------------------------------------
# Widget renderers (pure functions → rich renderables)
# ---------------------------------------------------------------------------

_STATUS_COLORS = {
    "pending": "dim",
    "blocked": "yellow",
    "in_progress": "blue bold",
    "completed": "green",
    "failed": "red bold",
    "skipped": "dim strikethrough",
}

_AGENT_ICONS = {
    "vision": "👁 ",
    "graph": "🔗",
    "migration": "📦",
    "heal": "🩹",
    "jury": "⚖️ ",
    "chat": "💬",
    "recipe": "📋",
    "index": "📇",
    "refactor": "🔧",
    "profiler": "⚡",
}


def render_sessions_panel(state: DashboardState) -> Panel:
    """Render the active sessions sidebar."""
    table = Table(show_header=True, header_style="bold cyan", expand=True, box=None)
    table.add_column("Session", style="cyan", no_wrap=True)
    table.add_column("Intent", style="white")

    if state.sessions:
        for s in state.sessions[:8]:
            name = s.display_name or s.session_id[:8]
            intent = s.active_intent[:30] if s.active_intent else "idle"
            table.add_row(name, intent)
    else:
        table.add_row("[dim]No active sessions[/dim]", "")

    return Panel(table, title="[bold cyan]Sessions[/bold cyan]", border_style="cyan")


def render_file_events_panel(state: DashboardState) -> Panel:
    """Render recent file change events."""
    table = Table(show_header=False, expand=True, box=None)
    table.add_column("File", style="white", ratio=3)
    table.add_column("Age", style="dim", no_wrap=True)

    if state.file_events:
        for ev in state.file_events[:8]:
            short_path = ev.file_path.split("/")[-1]
            color = {"created": "green", "deleted": "red"}.get(ev.event_type, "yellow")
            table.add_row(f"[{color}]{short_path}[/{color}]", ev.age_str())
    else:
        table.add_row("[dim]No recent changes[/dim]", "")

    return Panel(table, title="[bold yellow]Recent Changes[/bold yellow]", border_style="yellow")


def render_swarm_panel(state: DashboardState) -> Panel:
    """Render the swarm DAG as a tree view."""
    swarm = state.swarm

    if not swarm.tasks:
        content = Text("No active swarm. Type a goal in the command bar.", style="dim")
        return Panel(
            Align.center(content, vertical="middle"),
            title="[bold blue]Swarm DAG[/bold blue]",
            border_style="blue",
        )

    tree = Tree(f"[bold]{swarm.goal[:60]}[/bold]")

    task_map = {t.task_id: t for t in swarm.tasks}
    roots = [t for t in swarm.tasks if not t.dependencies]
    rendered = set()

    def _add_node(parent_tree: Tree, task: SwarmTaskView) -> None:
        if task.task_id in rendered:
            return
        rendered.add(task.task_id)

        icon = _AGENT_ICONS.get(task.agent_type, "⚙️ ")
        color = _STATUS_COLORS.get(task.status, "white")
        status_badge = f"[{color}]{task.status.upper()}[/{color}]"

        duration = ""
        if task.duration_ms > 0:
            duration = f" ({task.duration_ms:.0f}ms)"

        error = ""
        if task.error:
            error = f"\n  [red]✗ {task.error[:40]}[/red]"

        label = f"{icon} [{color}]{task.agent_type.upper()}[/{color}] {task.description[:40]} {status_badge}{duration}{error}"
        node = parent_tree.add(label)

        # Add children (tasks that depend on this one)
        for t in swarm.tasks:
            if task.task_id in t.dependencies and t.task_id not in rendered:
                _add_node(node, t)

    for root in roots:
        _add_node(tree, root)

    # Catch any unrendered tasks
    for t in swarm.tasks:
        if t.task_id not in rendered:
            _add_node(tree, t)

    # Progress bar
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        expand=True,
    )
    prog_task = progress.add_task(
        "Swarm", total=100, completed=int(swarm.progress * 100)
    )

    if swarm.is_complete:
        status_color = "green" if swarm.is_success else "red"
        status_text = "COMPLETE" if swarm.is_success else "FAILED"
        progress.update(prog_task, description=f"[{status_color}]{status_text}[/{status_color}]")

    content = Group(tree, progress)
    return Panel(content, title="[bold blue]Swarm DAG[/bold blue]", border_style="blue")


def render_graph_stats_panel(state: DashboardState) -> Panel:
    """Render dependency graph stats."""
    gs = state.graph_stats
    table = Table(show_header=False, expand=True, box=None)
    table.add_column("Metric", style="bold", ratio=2)
    table.add_column("Value", justify="right")

    table.add_row("Files", str(gs.total_files))
    table.add_row("Symbols", str(gs.total_symbols))
    table.add_row("Imports", str(gs.total_imports))
    cycles_style = "red bold" if gs.cycles > 0 else "green"
    table.add_row("Cycles", f"[{cycles_style}]{gs.cycles}[/{cycles_style}]")

    return Panel(table, title="[bold magenta]Graph Stats[/bold magenta]", border_style="magenta")


def render_hot_files_panel(state: DashboardState) -> Panel:
    """Render hot files (most dependents) with optional latency badges."""
    table = Table(show_header=False, expand=True, box=None)
    table.add_column("File", style="white", ratio=3)
    table.add_column("Latency", justify="right", style="dim", no_wrap=True)

    # Build latency lookup from perf hotspots
    latency_map: Dict[str, float] = {}
    for hs in state.graph_stats.perf_hotspots:
        fname = hs.get("file", "").split("/")[-1]
        latency_map[fname] = latency_map.get(fname, 0) + hs.get("totalTimeMs", 0)

    if state.graph_stats.hot_files:
        for f in state.graph_stats.hot_files[:6]:
            short = f.split("/")[-1]
            latency = latency_map.get(short, 0)
            if latency > 0:
                if latency > 1000:
                    badge = f"[bold red]{latency / 1000:.1f}s[/bold red]"
                else:
                    badge = f"[yellow]{latency:.0f}ms[/yellow]"
                table.add_row(f"[bold red]🔥[/bold red] {short}", badge)
            else:
                table.add_row(f"[bold red]🔥[/bold red] {short}", "")
    elif state.graph_stats.perf_hotspots:
        for hs in state.graph_stats.perf_hotspots[:6]:
            short = hs.get("file", "?").split("/")[-1]
            ms = hs.get("totalTimeMs", 0)
            badge = f"[bold red]{ms / 1000:.1f}s[/bold red]" if ms > 1000 else f"[yellow]{ms:.0f}ms[/yellow]"
            table.add_row(f"[bold red]⚡[/bold red] {short}", badge)
    else:
        table.add_row("[dim]No hot files[/dim]", "")

    return Panel(table, title="[bold red]Hot Files[/bold red]", border_style="red")


def render_noisy_recipes_panel(state: DashboardState) -> Panel:
    """Render noisiest recipes."""
    table = Table(show_header=False, expand=True, box=None)
    table.add_column("Recipe", style="white")
    table.add_column("Triggers", justify="right", style="yellow")

    if state.graph_stats.noisy_recipes:
        for r in state.graph_stats.noisy_recipes[:5]:
            table.add_row(r.get("id", "?"), str(r.get("count", 0)))
    else:
        table.add_row("[dim]No recipe data[/dim]", "")

    return Panel(table, title="[bold yellow]Noisy Recipes[/bold yellow]", border_style="yellow")


def render_drift_panel(state: DashboardState) -> Panel:
    """Render drift warnings in the sidebar."""
    table = Table(show_header=False, expand=True, box=None)
    table.add_column("Warning", style="white", ratio=3)
    table.add_column("Age", style="dim", no_wrap=True)

    if state.drift_warnings:
        for dw in state.drift_warnings[:6]:
            short_file = dw.file_path.split("/")[-1]
            sev_color = {"error": "red bold", "critical": "red bold", "warning": "yellow"}.get(dw.severity, "dim")
            label = f"[{sev_color}]\u26a0 {short_file}[/{sev_color}]: {dw.message[:40]}"
            table.add_row(label, dw.age_str())
    else:
        table.add_row("[dim]No drift warnings[/dim]", "")

    return Panel(table, title="[bold red]Drift Warnings[/bold red]", border_style="red")


def render_nexus_panel(state: DashboardState) -> Panel:
    """Render the Nexus multi-repo view."""
    nv = state.nexus
    if not nv.enabled:
        return Panel(
            Text("  Nexus disabled. Use --nexus to enable.", style="dim"),
            title="[bold magenta]Nexus[/bold magenta]",
            border_style="dim",
        )

    table = Table(show_header=True, header_style="bold magenta", expand=True, box=None)
    table.add_column("Repo", style="bold")
    table.add_column("Files", justify="right", style="cyan")
    table.add_column("Symbols", justify="right", style="green")
    table.add_column("Links", justify="right", style="yellow")

    for repo in nv.repos[:8]:
        deps = len(repo.get("dependents", []))
        table.add_row(
            repo.get("name", "?"),
            str(repo.get("fileCount", 0)),
            str(repo.get("symbolCount", 0)),
            str(deps),
        )

    if nv.high_risk:
        table.add_section()
        for hr in nv.high_risk[:3]:
            table.add_row(
                f"[red]⚠ {hr.get('symbolName', '?')}[/red]",
                "", str(hr.get("totalRepos", 0)),
                hr.get("severity", ""),
            )

    summary = Text.assemble(
        (f"  {nv.repo_count} repos", "magenta"),
        (f"  •  {nv.total_files} files", "dim"),
        (f"  •  {nv.cross_edges} cross-edges", "yellow"),
    )

    return Panel(
        Group(table, summary),
        title="[bold magenta]Nexus (Multi-Repo)[/bold magenta]",
        border_style="magenta",
    )


def render_command_bar(state: DashboardState) -> Panel:
    """Render the command input area."""
    if state.pending_plan:
        plan_info = state.pending_plan
        task_count = plan_info.get("taskCount", 0)
        goal = plan_info.get("goal", "")[:50]
        content = Text.assemble(
            ("PLAN READY: ", "bold green"),
            (f"{goal} ", "white"),
            (f"({task_count} tasks) ", "cyan"),
            ("Press [Enter] to execute or [Esc] to cancel", "dim"),
        )
    else:
        content = Text.assemble(
            ("➜ ", "bold green"),
            (state.status_message, "white"),
        )

    return Panel(content, title="[bold green]Command Bar[/bold green]", border_style="green", height=3)


def render_roi_ticker(state: DashboardState) -> Panel:
    """Render the ROI footer ticker."""
    roi = state.roi
    if roi.hours_saved > 0:
        hours = f"{roi.hours_saved:.1f}"
        content = Text.assemble(
            ("  ✨ code4u saved ", "dim"),
            (f"{hours} hours", "bold green"),
            (f" across {roi.repos_count} repos", "dim"),
            (f" • {roi.reviews_count} reviews", "dim"),
            (f" • {roi.accepted_count}/{roi.total_suggestions} suggestions accepted", "dim"),
            ("  ", ""),
        )
    else:
        content = Text("  ✨ code4u.ai — AI-native refactoring platform", style="dim")

    return Panel(content, border_style="green", height=3)


def build_layout(state: DashboardState) -> Layout:
    """Build the full 3-column dashboard layout."""
    layout = Layout()

    # Main vertical split: header, body, command bar, footer
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="command", size=3),
        Layout(name="footer", size=3),
    )

    # Header
    header_text = Text.assemble(
        ("  ⚡ code4u.ai War Room", "bold white on blue"),
        (f"  │  {state.workspace or 'No workspace'}", "dim"),
        (f"  │  {time.strftime('%H:%M:%S')}", "dim"),
    )
    layout["header"].update(Panel(header_text, border_style="blue", height=3))

    # Body: 3 columns
    layout["body"].split_row(
        Layout(name="sidebar", ratio=1),
        Layout(name="center", ratio=2),
        Layout(name="right", ratio=1),
    )

    # Sidebar: sessions + drift warnings + file events
    if state.drift_warnings:
        layout["sidebar"].split_column(
            Layout(name="sessions"),
            Layout(name="drift"),
            Layout(name="file_events"),
        )
        layout["drift"].update(render_drift_panel(state))
    else:
        layout["sidebar"].split_column(
            Layout(name="sessions"),
            Layout(name="file_events"),
        )
    layout["sessions"].update(render_sessions_panel(state))
    layout["file_events"].update(render_file_events_panel(state))

    # Center: swarm DAG
    layout["center"].update(render_swarm_panel(state))

    # Right: graph stats + nexus + hot files + noisy recipes
    if state.nexus.enabled:
        layout["right"].split_column(
            Layout(name="graph_stats"),
            Layout(name="nexus"),
            Layout(name="hot_files"),
        )
        layout["nexus"].update(render_nexus_panel(state))
    else:
        layout["right"].split_column(
            Layout(name="graph_stats"),
            Layout(name="hot_files"),
            Layout(name="noisy_recipes"),
        )
        layout["noisy_recipes"].update(render_noisy_recipes_panel(state))
    layout["graph_stats"].update(render_graph_stats_panel(state))
    layout["hot_files"].update(render_hot_files_panel(state))

    # Command bar
    layout["command"].update(render_command_bar(state))

    # Footer: ROI ticker
    layout["footer"].update(render_roi_ticker(state))

    return layout


# ---------------------------------------------------------------------------
# Data loaders (pull from backend state)
# ---------------------------------------------------------------------------

def load_graph_stats(workspace: str) -> GraphStats:
    """Load dependency graph stats from a workspace."""
    stats = GraphStats()
    if not workspace:
        return stats

    try:
        from pathlib import Path
        from code4u.code_intelligence.knowledge_graph.symbol_indexer import (
            SymbolIndexer,
            DependencyMap,
        )

        dep_map = DependencyMap()
        indexer = SymbolIndexer()
        indexer.index_workspace(workspace, dep_map)

        stats.total_files = len(dep_map.all_files)
        stats.total_symbols = sum(
            len(dep_map.get_symbol_defs(f)) for f in dep_map.all_files
        )
        stats.total_imports = sum(
            len(dep_map.get_imports(f)) for f in dep_map.all_files
        )

        cycles = dep_map.detect_cycles()
        stats.cycles = len(cycles)

        # Find hot files (most dependents)
        file_dep_counts: Dict[str, int] = {}
        for f in dep_map.all_files:
            for sym_def in dep_map.get_symbol_defs(f):
                deps = dep_map.get_dependents(sym_def.name)
                file_dep_counts[f] = file_dep_counts.get(f, 0) + len(deps)

        sorted_files = sorted(file_dep_counts.items(), key=lambda x: x[1], reverse=True)
        stats.hot_files = [f for f, _ in sorted_files[:6]]

    except Exception as exc:
        logger.warning("graph_stats_error", error=str(exc))

    return stats


def load_roi_data() -> ROIData:
    """Load ROI analytics from the AuditStore."""
    roi = ROIData()
    try:
        from code4u.models.analytics import AuditStore
        store = AuditStore()
        summary = store.summary()
        roi.total_suggestions = summary.get("totalSuggestions", 0)
        roi.accepted_count = summary.get("totalAccepted", 0)
        roi.minutes_saved = summary.get("totalMinutesSaved", 0)
        roi.hours_saved = roi.minutes_saved / 60.0
        roi.repos_count = len(summary.get("repos", {}))
        roi.reviews_count = summary.get("totalReviews", 0)
    except Exception:
        pass
    return roi


def load_nexus_view(workspace: str) -> NexusView:
    """Load Nexus multi-repo data from a workspace."""
    nv = NexusView()
    if not workspace:
        return nv

    try:
        from pathlib import Path
        from code4u.core.nexus import NexusContext
        from code4u.agents.nexus.impact_analyzer import ImpactAnalyzer

        nexus = NexusContext(workspace)
        repos = nexus.scan()
        if not repos:
            return nv

        nexus.index_all()
        nexus.link_repos()

        nv.enabled = True
        nv.repo_count = nexus.repo_count
        nv.total_files = nexus.registry.total_files
        nv.total_symbols = nexus.registry.total_symbols
        nv.cross_edges = nexus.registry.total_cross_edges
        nv.repos = [r.to_dict() for r in nexus.registry.repos.values()]

        analyzer = ImpactAnalyzer(nexus.registry)
        high_risk = analyzer.high_risk_symbols(min_repos=1)
        nv.high_risk = [b.to_dict() for b in high_risk[:5]]
    except Exception:
        pass

    return nv


def load_swarm_view_from_graph(graph_dict: Dict[str, Any]) -> SwarmView:
    """Convert a TaskGraph dict into a SwarmView."""
    sv = SwarmView(
        graph_id=graph_dict.get("id", ""),
        goal=graph_dict.get("goal", ""),
        progress=graph_dict.get("progress", 0.0),
        is_complete=graph_dict.get("isComplete", False),
        is_success=graph_dict.get("isSuccess", False),
    )
    for t in graph_dict.get("tasks", []):
        sv.tasks.append(SwarmTaskView(
            task_id=t.get("id", ""),
            agent_type=t.get("agentType", "refactor"),
            description=t.get("description", ""),
            status=t.get("status", "pending"),
            duration_ms=t.get("durationMs", 0.0),
            error=t.get("error", ""),
            dependencies=t.get("dependencies", []),
        ))
    return sv


# ---------------------------------------------------------------------------
# WarRoomDashboard
# ---------------------------------------------------------------------------

class WarRoomDashboard:
    """Interactive TUI dashboard for code4u.ai.

    Usage::

        dashboard = WarRoomDashboard(workspace="/path/to/project")
        dashboard.run()
    """

    def __init__(
        self,
        workspace: str = "",
        *,
        refresh_rate: float = 1.0,
        server_url: str = "http://localhost:8000",
    ) -> None:
        self.state = DashboardState(workspace=workspace)
        self.refresh_rate = refresh_rate
        self.server_url = server_url
        self._running = False
        self._on_command: Optional[Callable[[str], None]] = None

    def set_command_handler(self, handler: Callable[[str], None]) -> None:
        """Register a callback for when the user enters a command."""
        self._on_command = handler

    def update_swarm(self, graph_dict: Dict[str, Any]) -> None:
        """Update the swarm view from a TaskGraph dict."""
        self.state.swarm = load_swarm_view_from_graph(graph_dict)

    def update_swarm_event(self, event: Dict[str, Any]) -> None:
        """Process a swarm event and update state."""
        self.state.swarm.events.append(event)
        self.state.swarm.progress = event.get("progress", self.state.swarm.progress)

        task_data = event.get("task")
        if task_data:
            task_id = task_data.get("id", "")
            for t in self.state.swarm.tasks:
                if t.task_id == task_id:
                    t.status = task_data.get("status", t.status)
                    t.duration_ms = task_data.get("durationMs", t.duration_ms)
                    t.error = task_data.get("error", t.error)
                    break

        event_type = event.get("event", "")
        if event_type == "SWARM_COMPLETED":
            self.state.swarm.is_complete = True
            self.state.swarm.is_success = self.state.swarm.progress >= 1.0

    def add_file_event(self, file_path: str, event_type: str = "modified") -> None:
        """Add a file watcher event to the sidebar."""
        self.state.add_file_event(FileEvent(file_path=file_path, event_type=event_type))

    def add_drift_warning(self, warning: DriftWarning) -> None:
        """Add a drift violation to the sidebar."""
        self.state.add_drift_warning(warning)

    def add_session(self, session: SessionInfo) -> None:
        """Add or update a session in the sidebar."""
        for i, s in enumerate(self.state.sessions):
            if s.session_id == session.session_id:
                self.state.sessions[i] = session
                return
        self.state.sessions.append(session)

    def remove_session(self, session_id: str) -> None:
        """Remove a session from the sidebar."""
        self.state.sessions = [s for s in self.state.sessions if s.session_id != session_id]

    def set_pending_plan(self, plan: Optional[Dict[str, Any]]) -> None:
        """Set or clear a pending swarm plan for human-in-the-loop."""
        self.state.pending_plan = plan

    def refresh_stats(self) -> None:
        """Refresh graph stats, ROI data, and Nexus view from backend."""
        self.state.graph_stats = load_graph_stats(self.state.workspace)
        self.state.roi = load_roi_data()
        if self.state.nexus.enabled:
            self.state.nexus = load_nexus_view(self.state.workspace)

    def render(self) -> Layout:
        """Render the current state to a rich Layout."""
        return build_layout(self.state)

    def run(self, max_iterations: int = 0) -> None:
        """Run the dashboard in the terminal.

        If ``max_iterations`` > 0, runs for that many refresh cycles
        then exits (useful for testing). Otherwise runs until interrupted.
        """
        console = Console()
        self._running = True
        self.refresh_stats()

        iterations = 0
        try:
            with Live(
                self.render(),
                console=console,
                refresh_per_second=1.0 / self.refresh_rate if self.refresh_rate > 0 else 1,
                screen=max_iterations == 0,
            ) as live:
                while self._running:
                    live.update(self.render())
                    time.sleep(self.refresh_rate)
                    iterations += 1
                    if max_iterations > 0 and iterations >= max_iterations:
                        break
        except KeyboardInterrupt:
            pass
        finally:
            self._running = False

    def stop(self) -> None:
        """Signal the dashboard to stop."""
        self._running = False

    def handle_command(self, goal: str) -> Dict[str, Any]:
        """Process a command from the command bar.

        Calls the ChiefArchitect to decompose the goal, renders the
        plan, and returns the graph dict.
        """
        self.state.status_message = f"Planning: {goal[:50]}..."
        self.state.command_history.append(goal)

        from code4u.agents.orchestrator.chief import ChiefArchitect

        chief = ChiefArchitect()
        graph = chief.decompose(goal, workspace_path=self.state.workspace)
        graph_dict = graph.to_dict()

        self.update_swarm(graph_dict)
        self.set_pending_plan(graph_dict)
        self.state.status_message = f"Plan ready — {graph.task_count} tasks. Press Enter to execute."

        return graph_dict

    def execute_plan(self) -> Dict[str, Any]:
        """Execute the pending plan."""
        if not self.state.pending_plan:
            return {}

        from code4u.agents.orchestrator.chief import ChiefArchitect
        from code4u.agents.orchestrator.controller import SwarmController

        goal = self.state.pending_plan.get("goal", "")
        self.state.status_message = f"Executing: {goal[:50]}..."
        self.set_pending_plan(None)

        chief = ChiefArchitect()
        graph = chief.decompose(goal, workspace_path=self.state.workspace)

        controller = SwarmController()
        controller.set_event_callback(lambda e: self.update_swarm_event(e))

        result = controller.execute_sync(graph)
        result_dict = result.to_dict()
        self.update_swarm(result_dict)

        status = "✓ Complete" if result.is_success else "✗ Failed"
        self.state.status_message = f"{status} — {result.completed_count}/{result.task_count} tasks"

        return result_dict

    def cancel_plan(self) -> None:
        """Cancel a pending plan without executing."""
        self.set_pending_plan(None)
        self.state.swarm = SwarmView()
        self.state.status_message = "Plan cancelled. Ready."
