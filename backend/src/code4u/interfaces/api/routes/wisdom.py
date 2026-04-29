"""Collective Intelligence & Wisdom API routes.

Endpoints:
  - POST /wisdom/nuggets/store       — store a wisdom nugget
  - GET  /wisdom/nuggets             — list all nuggets
  - POST /wisdom/nuggets/search      — search nuggets
  - GET  /wisdom/stats               — get wisdom store stats
  - POST /wisdom/analyze             — analyze code for suggestions
  - POST /wisdom/find-duplicates     — find semantic duplicates
  - GET  /wisdom/suggestions         — get latest suggestions
  - GET  /wisdom/report              — get latest wisdom report
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from code4u.knowledge.pattern_extractor import get_pattern_extractor
from code4u.agents.wisdom_agent import WisdomAgent

router = APIRouter(prefix="/wisdom", tags=["Collective Intelligence"])

_wisdom_agent = WisdomAgent()
_last_report: str = ""


class StoreNuggetRequest(BaseModel):
    before: str = Field(..., description="Code before fix")
    after: str = Field(..., description="Code after fix")
    language: str = Field("python", description="Programming language")
    pattern_type: str = Field("bug_fix", description="security_fix, performance_fix, bug_fix, refactor, accessibility_fix")
    description: str = Field("", description="Human-readable description")
    tags: List[str] = Field(default_factory=list)
    source_project: str = Field("", description="Project identifier (will be hashed)")


class SearchNuggetsRequest(BaseModel):
    query: str = Field(..., description="Search query")
    language: Optional[str] = Field(None, description="Filter by language")
    pattern_type: Optional[str] = Field(None, description="Filter by type")
    limit: int = Field(10, description="Max results")


class AnalyzeRequest(BaseModel):
    code_map: Dict[str, str] = Field(..., description="filepath -> content")
    failures: List[Dict[str, Any]] = Field(default_factory=list)


class FindDuplicatesRequest(BaseModel):
    code_map: Dict[str, str] = Field(..., description="filepath -> content")
    project_name: str = Field("", description="Current project name")


@router.post("/nuggets/store")
async def store_nugget(request: StoreNuggetRequest) -> Dict[str, Any]:
    extractor = get_pattern_extractor()
    nugget = extractor.extract_pattern(
        before=request.before,
        after=request.after,
        language=request.language,
        pattern_type=request.pattern_type,
        description=request.description,
        tags=request.tags if request.tags else None,
        source_project=request.source_project,
    )
    return nugget.to_dict()


@router.get("/nuggets")
async def list_nuggets(limit: int = 50) -> Dict[str, Any]:
    extractor = get_pattern_extractor()
    nuggets = extractor.get_all_nuggets()
    return {
        "nuggets": [n.to_dict() for n in nuggets[-limit:]],
        "total": len(nuggets),
    }


@router.post("/nuggets/search")
async def search_nuggets(request: SearchNuggetsRequest) -> Dict[str, Any]:
    extractor = get_pattern_extractor()
    results = extractor.search_nuggets(
        query=request.query,
        language=request.language,
        pattern_type=request.pattern_type,
        limit=request.limit,
    )
    return {"results": [n.to_dict() for n in results], "total": len(results)}


@router.get("/stats")
async def get_wisdom_stats() -> Dict[str, Any]:
    extractor = get_pattern_extractor()
    return extractor.get_stats()


@router.post("/analyze")
async def analyze_code(request: AnalyzeRequest) -> Dict[str, Any]:
    global _last_report
    suggestions = _wisdom_agent.analyze_code_for_suggestions(
        code_map=request.code_map,
        failures=request.failures if request.failures else None,
    )
    _last_report = _wisdom_agent.generate_report(suggestions)
    return {
        "suggestions": [s.to_dict() for s in suggestions],
        "total": len(suggestions),
    }


@router.post("/find-duplicates")
async def find_duplicates(request: FindDuplicatesRequest) -> Dict[str, Any]:
    duplicates = _wisdom_agent.find_semantic_duplicates(
        code_map=request.code_map,
        project_name=request.project_name,
    )
    return {
        "duplicates": [d.to_dict() for d in duplicates],
        "total": len(duplicates),
    }


@router.get("/suggestions")
async def get_suggestions() -> Dict[str, Any]:
    suggestions = _wisdom_agent.get_suggestions()
    return {"suggestions": [s.to_dict() for s in suggestions], "total": len(suggestions)}


@router.get("/report", response_class=PlainTextResponse)
async def get_wisdom_report() -> str:
    return _last_report or "# No analysis has been run yet.\n\nRun POST /wisdom/analyze first."
