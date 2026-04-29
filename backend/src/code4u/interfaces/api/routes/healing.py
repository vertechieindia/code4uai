"""Healing API — automated error diagnosis and repair.

Endpoints:
  - ``POST /heal``             — diagnose raw error output and suggest fixes.
  - ``POST /heal/run``         — run tests, diagnose failures, suggest fixes.
  - ``POST /heal/parse``       — parse stack traces only (no diagnosis).
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


class HealRequest(BaseModel):
    errorOutput: str = Field(..., description="Raw stderr / test output.")
    workspacePath: str = Field(..., description="Workspace root for indexing.")


class HealRunRequest(BaseModel):
    command: str = Field("pytest", description="Test runner command.")
    workspacePath: str = Field(..., description="Workspace root.")
    extraArgs: List[str] = Field(default_factory=list)
    timeout: int = Field(120, description="Max seconds.")


class ParseRequest(BaseModel):
    output: str = Field(..., description="Raw test runner output.")


def _get_dep_map(workspace: str):
    from code4u.code_intelligence.knowledge_graph.symbol_indexer import SymbolIndexer
    return SymbolIndexer().index_workspace(workspace, use_cache=True)


@router.post("/heal")
async def heal_from_output(request: HealRequest):
    """Diagnose raw error output and return repair suggestions."""
    from code4u.core.executor_ext import TestRunner

    dep_map = _get_dep_map(request.workspacePath)
    runner = TestRunner(dep_map)
    result = runner.diagnose_output(request.errorOutput)

    return {
        "errorCount": result.error_count,
        "fixCount": result.fix_count,
        "diagnoses": [d.to_dict() for d in result.diagnoses],
        "errors": [e.to_dict() for e in result.errors],
    }


@router.post("/heal/run")
async def heal_run_tests(request: HealRunRequest):
    """Run a test command, diagnose failures, and suggest fixes."""
    from code4u.core.executor_ext import TestRunner

    dep_map = _get_dep_map(request.workspacePath)
    runner = TestRunner(dep_map)
    result = runner.run(
        command=request.command,
        workspace=request.workspacePath,
        timeout=request.timeout,
        extra_args=request.extraArgs if request.extraArgs else None,
    )

    return {"result": result.to_dict()}


@router.post("/heal/parse")
async def parse_errors(request: ParseRequest):
    """Parse stack traces without diagnosis (lightweight)."""
    from code4u.agents.healing.parser import StackTraceParser

    parser = StackTraceParser()
    errors = parser.parse(request.output)
    language = parser.detect_language(request.output)

    return {
        "language": language.value,
        "errorCount": len(errors),
        "errors": [e.to_dict() for e in errors],
    }
