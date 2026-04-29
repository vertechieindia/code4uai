"""API routes for autocomplete service."""

from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import List, Optional
import time

from code4u.ai_engine.autocomplete import (
    AutocompleteEngine,
    CompletionRequest as AutocompleteRequest,
    CompletionResponse as AutocompleteResponse,
    InlineCompletionRequest as InlineRequest,
    InlineCompletionResponse as InlineResponse,
    ContextFile,
)


router = APIRouter(prefix="/autocomplete", tags=["autocomplete"])

# Singleton engine instance
_engine: Optional[AutocompleteEngine] = None


def get_engine() -> AutocompleteEngine:
    """Get or create autocomplete engine."""
    global _engine
    if _engine is None:
        _engine = AutocompleteEngine()
    return _engine


class ContextFileModel(BaseModel):
    """API model for context file."""
    path: str
    content: str


class CompletionRequestModel(BaseModel):
    """API request for completions."""
    file_path: str
    content: str
    cursor_line: int
    cursor_column: int
    language: str
    context_files: List[ContextFileModel] = []
    max_completions: int = 5
    include_documentation: bool = True


class CompletionModel(BaseModel):
    """API model for a single completion."""
    text: str
    display_text: str
    type: str
    score: float
    documentation: Optional[str] = None
    insert_text: Optional[str] = None
    detail: Optional[str] = None


class CompletionResponseModel(BaseModel):
    """API response for completions."""
    completions: List[CompletionModel]
    cache_hit: bool = False
    latency_ms: float = 0.0
    model_version: str = "1.0.0"


class InlineCompletionRequestModel(BaseModel):
    """API request for inline completion."""
    file_path: str
    content: str
    cursor_line: int
    cursor_column: int
    language: str
    prefix: str
    suffix: str
    max_tokens: int = 256
    temperature: float = 0.1


class InlineCompletionResponseModel(BaseModel):
    """API response for inline completion."""
    suggestion: Optional[str]
    multi_line: bool = False
    confidence: float = 0.0
    latency_ms: float = 0.0
    stop_reason: Optional[str] = None


@router.post("/complete", response_model=CompletionResponseModel)
async def get_completions(
    request: CompletionRequestModel,
    x_tenant_id: str = Header(default="default"),
    engine: AutocompleteEngine = Depends(get_engine),
) -> CompletionResponseModel:
    """Get code completions for the given context.
    
    Args:
        request: Completion request with code context
        x_tenant_id: Tenant ID for isolation
        engine: Autocomplete engine
        
    Returns:
        List of completion suggestions
    """
    try:
        # Convert to internal request
        internal_request = AutocompleteRequest(
            file_path=request.file_path,
            content=request.content,
            cursor_line=request.cursor_line,
            cursor_column=request.cursor_column,
            language=request.language,
            context_files=[
                ContextFile(path=cf.path, content=cf.content)
                for cf in request.context_files
            ],
            max_completions=request.max_completions,
            include_documentation=request.include_documentation,
            tenant_id=x_tenant_id,
        )
        
        # Get completions
        response = await engine.complete(internal_request)
        
        return CompletionResponseModel(
            completions=[
                CompletionModel(
                    text=c.text,
                    display_text=c.display_text,
                    type=c.type.value,
                    score=c.score,
                    documentation=c.documentation,
                    insert_text=c.insert_text,
                    detail=c.detail,
                )
                for c in response.completions
            ],
            cache_hit=response.cache_hit,
            latency_ms=response.latency_ms,
            model_version=response.model_version,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/inline", response_model=InlineCompletionResponseModel)
async def get_inline_completion(
    request: InlineCompletionRequestModel,
    x_tenant_id: str = Header(default="default"),
    engine: AutocompleteEngine = Depends(get_engine),
) -> InlineCompletionResponseModel:
    """Get inline (Tab) completion suggestion.
    
    Args:
        request: Inline completion request
        x_tenant_id: Tenant ID for isolation
        engine: Autocomplete engine
        
    Returns:
        Inline completion suggestion
    """
    try:
        # Convert to internal request
        internal_request = InlineRequest(
            file_path=request.file_path,
            content=request.content,
            cursor_line=request.cursor_line,
            cursor_column=request.cursor_column,
            language=request.language,
            prefix=request.prefix,
            suffix=request.suffix,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            tenant_id=x_tenant_id,
        )
        
        # Get inline completion
        response = await engine.inline_complete(internal_request)
        
        return InlineCompletionResponseModel(
            suggestion=response.suggestion,
            multi_line=response.multi_line,
            confidence=response.confidence,
            latency_ms=response.latency_ms,
            stop_reason=response.stop_reason,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class TabToJumpRequest(BaseModel):
    """Request for Tab-to-Jump suggestion."""
    file_path: str
    content: str
    cursor_line: int
    cursor_column: int
    language: str


class TabToJumpResponse(BaseModel):
    """Response for Tab-to-Jump suggestion."""
    file_path: Optional[str]
    line: Optional[int]
    column: Optional[int]
    preview: Optional[str]
    confidence: float = 0.0
    reason: Optional[str] = None


@router.post("/tab-jump", response_model=TabToJumpResponse)
async def get_tab_jump_suggestion(
    request: TabToJumpRequest,
    engine: AutocompleteEngine = Depends(get_engine),
) -> TabToJumpResponse:
    """Get Tab-to-Jump suggestion for next edit location.
    
    Args:
        request: Tab jump request
        engine: Autocomplete engine
        
    Returns:
        Jump location suggestion
    """
    try:
        suggestion = await engine.suggest_jump(
            file_path=request.file_path,
            content=request.content,
            cursor_line=request.cursor_line,
            cursor_column=request.cursor_column,
            language=request.language,
        )
        
        if suggestion:
            return TabToJumpResponse(
                file_path=suggestion.file_path,
                line=suggestion.line,
                column=suggestion.column,
                preview=suggestion.preview,
                confidence=suggestion.confidence,
                reason=suggestion.reason,
            )
        
        return TabToJumpResponse(confidence=0.0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class TabToImportRequest(BaseModel):
    """Request for Tab-to-Import suggestion."""
    file_path: str
    content: str
    cursor_line: int
    cursor_column: int
    language: str
    symbol: str


class TabToImportResponse(BaseModel):
    """Response for Tab-to-Import suggestion."""
    import_statement: Optional[str]
    symbol: Optional[str]
    source_module: Optional[str]
    confidence: float = 0.0


@router.post("/tab-import", response_model=TabToImportResponse)
async def get_tab_import_suggestion(
    request: TabToImportRequest,
    engine: AutocompleteEngine = Depends(get_engine),
) -> TabToImportResponse:
    """Get Tab-to-Import suggestion for undefined symbol.
    
    Args:
        request: Tab import request
        engine: Autocomplete engine
        
    Returns:
        Import suggestion
    """
    try:
        suggestion = await engine.suggest_import(
            file_path=request.file_path,
            content=request.content,
            cursor_line=request.cursor_line,
            cursor_column=request.cursor_column,
            language=request.language,
            symbol=request.symbol,
        )
        
        if suggestion:
            return TabToImportResponse(
                import_statement=suggestion.import_statement,
                symbol=suggestion.symbol,
                source_module=suggestion.source_module,
                confidence=suggestion.confidence,
            )
        
        return TabToImportResponse(confidence=0.0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def autocomplete_health():
    """Health check for autocomplete service."""
    return {"status": "healthy", "service": "autocomplete"}

