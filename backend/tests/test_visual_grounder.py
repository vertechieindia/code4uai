"""Tests for the Visual Grounding pipeline.

Verifies that ``VisualGrounder`` can map intents + codebase structure
to the correct files and symbols, and that the UI layout intent
classifier detects layout-related intents.
"""

from __future__ import annotations

import asyncio
import textwrap
from pathlib import Path
from typing import Dict

import pytest

from code4u.ai_engine.llm.visual_grounder import (
    VisualGrounder,
    GroundingResult,
    build_codebase_summary,
)
from code4u.code_intelligence.knowledge_graph.symbol_indexer import (
    DependencyMap,
    SymbolIndexer,
)
from code4u.platform_core.agents.orchestrator import PlanExecutor
from code4u.platform_core.agents.proposed_plan import INTENT_UI_LAYOUT


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

HEADER_TSX = textwrap.dedent("""\
    import React from 'react';

    export function Header({ title }) {
        return <header className="header">{title}</header>;
    }
""")

SIDEBAR_TSX = textwrap.dedent("""\
    import React from 'react';

    export function Sidebar({ items }) {
        return (
            <nav className="sidebar">
                {items.map(i => <div key={i}>{i}</div>)}
            </nav>
        );
    }
""")

APP_TSX = textwrap.dedent("""\
    import React from 'react';
    import { Header } from './Header';
    import { Sidebar } from './Sidebar';

    export function App() {
        return (
            <div className="app">
                <Header title="My App" />
                <Sidebar items={['Home', 'Settings']} />
            </div>
        );
    }
""")

STYLES_CSS = textwrap.dedent("""\
    .header { background: #333; color: white; padding: 1rem; }
    .sidebar { width: 200px; background: #f0f0f0; }
    .app { display: flex; flex-direction: column; }
""")

UTILS_PY = textwrap.dedent("""\
    def calculate_total(items):
        return sum(item.price for item in items)
""")

PROJECT_FILES: Dict[str, str] = {
    "Header.tsx": HEADER_TSX,
    "Sidebar.tsx": SIDEBAR_TSX,
    "App.tsx": APP_TSX,
    "styles.css": STYLES_CSS,
    "utils.py": UTILS_PY,
}


@pytest.fixture
def ui_project(tmp_path: Path):
    """Create a mixed UI + Python project."""
    for name, content in PROJECT_FILES.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    yield tmp_path


@pytest.fixture
def dep_map(ui_project: Path) -> DependencyMap:
    indexer = SymbolIndexer()
    return indexer.index_workspace(str(ui_project))


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Test: Codebase summary
# ---------------------------------------------------------------------------

class TestCodebaseSummary:
    def test_summary_includes_files(self, dep_map: DependencyMap):
        summary = build_codebase_summary(dep_map)
        assert "Header.tsx" in summary
        assert "Sidebar.tsx" in summary
        assert "App.tsx" in summary
        assert "utils.py" in summary

    def test_summary_includes_symbols(self, dep_map: DependencyMap):
        summary = build_codebase_summary(dep_map)
        assert "Header" in summary or "header" in summary.lower()


# ---------------------------------------------------------------------------
# Test: Local grounding (keyword-based)
# ---------------------------------------------------------------------------

class TestLocalGrounding:
    def test_header_intent_matches_header_file(self, dep_map: DependencyMap):
        grounder = VisualGrounder(dep_map=dep_map)
        result = _run(grounder.ground(
            image_base64="fake",
            intent="Update the Header component",
        ))

        assert isinstance(result, GroundingResult)
        matched_names = [Path(f).name for f in result.matched_files]
        assert "Header.tsx" in matched_names

    def test_sidebar_intent_matches_sidebar(self, dep_map: DependencyMap):
        grounder = VisualGrounder(dep_map=dep_map)
        result = _run(grounder.ground(
            image_base64="fake",
            intent="Move the sidebar to the right",
        ))

        matched_names = [Path(f).name for f in result.matched_files]
        assert "Sidebar.tsx" in matched_names
        assert result.is_ui_layout is True

    def test_ui_intent_prioritizes_ui_files(self, dep_map: DependencyMap):
        grounder = VisualGrounder(dep_map=dep_map)
        result = _run(grounder.ground(
            image_base64="fake",
            intent="Redesign the app layout with new header",
        ))

        assert result.is_ui_layout is True
        for sym in result.matched_symbols:
            assert sym.confidence > 0

    def test_non_ui_intent(self, dep_map: DependencyMap):
        grounder = VisualGrounder(dep_map=dep_map)
        result = _run(grounder.ground(
            image_base64="fake",
            intent="Optimize calculate_total for performance",
        ))

        matched_names = [Path(f).name for f in result.matched_files]
        assert "utils.py" in matched_names
        assert result.is_ui_layout is False

    def test_metadata_structure(self, dep_map: DependencyMap):
        grounder = VisualGrounder(dep_map=dep_map)
        result = _run(grounder.ground(
            image_base64="fake",
            intent="Update the Header",
        ))

        meta = result.metadata
        assert "matchedFiles" in meta
        assert "matchedSymbols" in meta
        assert "visualSummary" in meta
        assert "isUiLayout" in meta


# ---------------------------------------------------------------------------
# Test: UI Layout intent classification
# ---------------------------------------------------------------------------

class TestUILayoutClassification:
    def test_move_sidebar(self):
        assert PlanExecutor._is_ui_layout_intent("Move the sidebar to the right")

    def test_make_it_look(self):
        assert PlanExecutor._is_ui_layout_intent("Make it look like this")

    def test_css_change(self):
        assert PlanExecutor._is_ui_layout_intent("CSS change for the header")

    def test_layout_prefix(self):
        assert PlanExecutor._is_ui_layout_intent("[UI Layout] Move header down")

    def test_normal_rename_is_not_layout(self):
        assert not PlanExecutor._is_ui_layout_intent("Rename foo to bar")

    def test_extract_is_not_layout(self):
        assert not PlanExecutor._is_ui_layout_intent("Extract calculate to utils.py")

    def test_rearrange_navbar(self):
        assert PlanExecutor._is_ui_layout_intent("Rearrange the navbar items")

    def test_swap_left_right(self):
        assert PlanExecutor._is_ui_layout_intent("Swap the left and right panels")


# ---------------------------------------------------------------------------
# Test: GroundingResult metadata in ProposedPlan
# ---------------------------------------------------------------------------

class TestVisualMetadataInPlan:
    def test_proposed_plan_includes_visual_metadata(self):
        from code4u.platform_core.agents.proposed_plan import ProposedPlan

        plan = ProposedPlan(
            intent="test",
            intent_type="ui_layout",
            visual_reasoning_metadata={
                "matchedFiles": ["Header.tsx"],
                "visualSummary": "A header component",
            },
        )

        summary = plan.summary
        assert "visualReasoningMetadata" in summary
        assert summary["visualReasoningMetadata"]["matchedFiles"] == ["Header.tsx"]

    def test_no_metadata_when_empty(self):
        from code4u.platform_core.agents.proposed_plan import ProposedPlan

        plan = ProposedPlan(intent="test", intent_type="rename")
        summary = plan.summary
        assert "visualReasoningMetadata" not in summary
