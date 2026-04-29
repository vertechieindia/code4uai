"""API routes for Supercomplete."""

from __future__ import annotations
from fastapi import APIRouter, Header
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from code4u.ai_engine.supercomplete import SupercompleteEngine, TabEngine
from code4u.ai_engine.supercomplete.engine import SupercompleteRequest, CursorPosition


router = APIRouter(prefix="/supercomplete", tags=["supercomplete"])

# Instances
_engines: Dict[str, SupercompleteEngine] = {}
_tab_engine = TabEngine()


def get_engine(tenant_id: str) -> SupercompleteEngine:
    if tenant_id not in _engines:
        _engines[tenant_id] = SupercompleteEngine(tenant_id)
    return _engines[tenant_id]


# ============= Request/Response Models =============

class CompletionRequest(BaseModel):
    """Request for completion."""
    file_path: str
    line: int
    column: int
    prefix: str
    suffix: str
    file_content: str
    language: str = "python"
    max_tokens: int = 500
    include_next_steps: bool = True


class CompletionItem(BaseModel):
    """A completion item."""
    id: str
    type: str
    text: str
    label: str
    detail: str = ""
    confidence: float = 0.9
    edit_predictions: List[Dict[str, Any]] = []


class CompletionResponse(BaseModel):
    """Response with completions."""
    completions: List[CompletionItem]
    latency_ms: float = 0.0
    cache_hit: bool = False


class TabRequest(BaseModel):
    """Request for tab action."""
    file_path: str
    cursor_line: int
    cursor_column: int
    has_completion: bool = False
    completion_text: Optional[str] = None
    in_placeholder: bool = False
    placeholder_index: int = 0
    total_placeholders: int = 0
    has_missing_import: bool = False
    missing_import: Optional[str] = None


class TabResponse(BaseModel):
    """Response for tab action."""
    action: str
    text_to_insert: Optional[str] = None
    jump_to_line: Optional[int] = None
    jump_to_column: Optional[int] = None
    import_text: Optional[str] = None
    import_line: int = 0


# ============= Endpoints =============

@router.post("/complete", response_model=CompletionResponse)
async def complete(
    request: CompletionRequest,
    x_tenant_id: str = Header(default="default"),
) -> CompletionResponse:
    """Get code completions."""
    engine = get_engine(x_tenant_id)
    
    sc_request = SupercompleteRequest(
        file_path=request.file_path,
        cursor=CursorPosition(
            line=request.line,
            column=request.column,
            file_path=request.file_path,
        ),
        prefix=request.prefix,
        suffix=request.suffix,
        file_content=request.file_content,
        language=request.language,
        max_tokens=request.max_tokens,
        include_next_steps=request.include_next_steps,
        tenant_id=x_tenant_id,
    )
    
    response = await engine.complete(sc_request)
    
    return CompletionResponse(
        completions=[
            CompletionItem(
                id=c.id,
                type=c.type.value,
                text=c.text,
                label=c.label,
                detail=c.detail,
                confidence=c.confidence,
                edit_predictions=[
                    {"placeholder": p.placeholder, "suggestion": p.suggestion}
                    for p in c.edit_predictions
                ],
            )
            for c in response.completions
        ],
        latency_ms=response.latency_ms,
        cache_hit=response.cache_hit,
    )


@router.post("/tab", response_model=TabResponse)
async def process_tab(
    request: TabRequest,
    x_tenant_id: str = Header(default="default"),
) -> TabResponse:
    """Process tab key press."""
    from code4u.ai_engine.supercomplete.tab_engine import TabContext
    
    context = TabContext(
        file_path=request.file_path,
        cursor_line=request.cursor_line,
        cursor_column=request.cursor_column,
        has_completion=request.has_completion,
        completion_text=request.completion_text,
        in_placeholder=request.in_placeholder,
        placeholder_index=request.placeholder_index,
        total_placeholders=request.total_placeholders,
        has_missing_import=request.has_missing_import,
        missing_import=request.missing_import,
    )
    
    result = _tab_engine.process_tab(context)
    
    return TabResponse(
        action=result.action.value,
        text_to_insert=result.text_to_insert,
        jump_to_line=result.jump_to_line,
        jump_to_column=result.jump_to_column,
        import_text=result.import_text,
        import_line=result.import_line,
    )


@router.post("/{completion_id}/accept")
async def accept_completion(
    completion_id: str,
    accepted: bool = True,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, str]:
    """Record completion acceptance."""
    engine = get_engine(x_tenant_id)
    await engine.accept_completion(completion_id, accepted)
    return {"status": "recorded"}


@router.post("/cache/clear")
async def clear_cache(
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, str]:
    """Clear completion cache."""
    engine = get_engine(x_tenant_id)
    engine.clear_cache()
    return {"status": "cleared"}

