from __future__ import annotations
"""Internal LLM API endpoints for code4u.ai.

These endpoints are intent-based, NOT raw chat.
Each endpoint:
- Compiles structured context
- Calls the model
- Enforces schema output
- Rejects hallucinations
"""
from typing import Any, Optional, List, Dict
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
import structlog

from code4u.ai_engine.llm.client import LLMClient, LLMRequest
from code4u.ai_engine.llm.router import ModelRouter
from code4u.code_intelligence.context.compiler import ContextCompiler
from code4u.code_intelligence.context.planner import ChangePlanner

router = APIRouter(prefix="/internal", tags=["Internal LLM"])
logger = structlog.get_logger("api.llm")

# Lazy-initialized clients
_llm_client: Optional[LLMClient] = None
_router: Optional[ModelRouter] = None
_compiler: Optional[ContextCompiler] = None
_planner: Optional[ChangePlanner] = None


def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


def get_router() -> ModelRouter:
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router


def get_compiler() -> ContextCompiler:
    global _compiler
    if _compiler is None:
        _compiler = ContextCompiler()
    return _compiler


def get_planner() -> ChangePlanner:
    global _planner
    if _planner is None:
        _planner = ChangePlanner()
    return _planner


# ============================================================================
# Request/Response Models
# ============================================================================

class GenerateDiffRequest(BaseModel):
    """Request to generate a unified diff."""
    intent: str = Field(..., description="What change to make")
    file_path: str = Field(..., description="Path to the file")
    file_content: str = Field(..., description="Current file content")
    selection: Optional[Dict[str, int]] = Field(None, description="Line selection {start, end}")
    constraints: List[str] = Field(default_factory=list, description="Additional constraints")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")


class GenerateDiffResponse(BaseModel):
    """Response with generated diff."""
    success: bool
    diff: str
    explanation: Optional[str] = None
    breaking_change: bool = False
    affected_components: List[str] = []
    model_used: str = ""
    latency_ms: float = 0


class ValidateSchemaRequest(BaseModel):
    """Request to validate schema compatibility."""
    old_schema: str
    new_schema: str
    schema_type: str = "pydantic"


class ValidateSchemaResponse(BaseModel):
    """Schema validation result."""
    compatible: bool
    breaking_changes: List[str] = []
    warnings: List[str] = []
    suggestions: List[str] = []


class ExplainChangeRequest(BaseModel):
    """Request to explain a diff."""
    diff: str
    context: Dict[str, Any] = {}


class ExplainChangeResponse(BaseModel):
    """Change explanation."""
    summary: str
    affected_components: List[str] = []
    risks: List[str] = []
    breaking_change: bool = False


class RefactorModuleRequest(BaseModel):
    """Request to refactor a module."""
    module_path: str
    refactor_type: str = Field(..., description="Type: rename, extract, inline, move")
    target: str = Field(..., description="What to refactor")
    new_name: Optional[str] = None
    destination: Optional[str] = None


class AnalyzeImpactRequest(BaseModel):
    """Request to analyze change impact."""
    file_path: str
    change_type: str = "modify"


class AnalyzeImpactResponse(BaseModel):
    """Impact analysis result."""
    blast_radius: Dict[str, int]
    affected_files: List[str]
    affected_teams: List[str]
    breaking_change: bool
    change_plan: Dict[str, Any]


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/generate-diff", response_model=GenerateDiffResponse)
async def generate_diff(request: GenerateDiffRequest):
    """
    Generate a unified diff for code changes.
    
    This is the PRIMARY endpoint for code generation.
    Output is constrained to unified diff format only.
    """
    logger.info("generate_diff_request", intent=request.intent, file=request.file_path)
    
    try:
        client = get_llm_client()
        router = get_router()
        
        # Build context
        context = {
            "language": _detect_language(request.file_path),
            "file_path": request.file_path,
            **request.context
        }
        
        # Route to appropriate model
        routing = router.route(
            task_type="generate_diff",
            context=context,
            estimated_tokens=len(request.file_content) // 4
        )
        
        # Generate diff
        diff = await client.generate_diff(
            instruction=request.intent,
            context=context,
            input_code=request.file_content,
            constraints=request.constraints
        )
        
        # Check for rejection
        if "INSUFFICIENT_CONTEXT" in diff:
            return GenerateDiffResponse(
                success=False,
                diff="",
                explanation="Insufficient context to generate change. Please provide more details.",
                model_used=routing["model"]
            )
        
        # Validate diff format
        if not _is_valid_diff(diff):
            logger.warning("invalid_diff_format", diff=diff[:200])
            return GenerateDiffResponse(
                success=False,
                diff="",
                explanation="Model generated invalid diff format. Retry with clearer instructions.",
                model_used=routing["model"]
            )
        
        return GenerateDiffResponse(
            success=True,
            diff=diff,
            breaking_change=_detect_breaking_change(diff),
            affected_components=_extract_affected_components(diff),
            model_used=routing["model"],
            latency_ms=0  # TODO: Add actual latency
        )
        
    except Exception as e:
        logger.error("generate_diff_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate-schema", response_model=ValidateSchemaResponse)
async def validate_schema(request: ValidateSchemaRequest):
    """
    Validate schema compatibility between versions.
    
    Detects:
    - Breaking changes (removed fields, type changes)
    - Warnings (new required fields)
    - Suggestions for backward compatibility
    """
    logger.info("validate_schema_request", schema_type=request.schema_type)
    
    try:
        client = get_llm_client()
        from code4u.ai_engine.llm.prompts import PromptBuilder
        
        prompt = PromptBuilder.build_schema_validation_prompt(
            old_schema=request.old_schema,
            new_schema=request.new_schema,
            schema_type=request.schema_type
        )
        
        response = await client.generate(LLMRequest(
            messages=[
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user}
            ],
            temperature=0.0,
            max_tokens=1024
        ))
        
        # Parse JSON response
        import json
        try:
            result = json.loads(response.content)
            return ValidateSchemaResponse(**result)
        except json.JSONDecodeError:
            logger.warning("schema_validation_parse_error", content=response.content[:200])
            return ValidateSchemaResponse(
                compatible=True,
                warnings=["Could not parse validation result"]
            )
            
    except Exception as e:
        logger.error("validate_schema_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/explain-change", response_model=ExplainChangeResponse)
async def explain_change(request: ExplainChangeRequest):
    """
    Explain what a diff does in plain language.
    
    Useful for:
    - PR descriptions
    - Change impact summaries
    - Team notifications
    """
    logger.info("explain_change_request")
    
    try:
        client = get_llm_client()
        from code4u.ai_engine.llm.prompts import PromptBuilder
        
        prompt = PromptBuilder.build_explain_prompt(
            diff=request.diff,
            context=request.context
        )
        
        response = await client.generate(LLMRequest(
            messages=[
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user}
            ],
            temperature=0.0,
            max_tokens=512
        ))
        
        import json
        try:
            result = json.loads(response.content)
            return ExplainChangeResponse(**result)
        except json.JSONDecodeError:
            return ExplainChangeResponse(
                summary=response.content[:500],
                affected_components=[],
                risks=[],
                breaking_change=False
            )
            
    except Exception as e:
        logger.error("explain_change_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refactor-module", response_model=GenerateDiffResponse)
async def refactor_module(request: RefactorModuleRequest):
    """
    Perform structured refactoring on a module.
    
    Supported types:
    - rename: Rename a symbol
    - extract: Extract function/component
    - inline: Inline a function/variable
    - move: Move to different location
    """
    logger.info(
        "refactor_module_request",
        module=request.module_path,
        type=request.refactor_type,
        target=request.target
    )
    
    try:
        # Read module content
        from pathlib import Path
        content = Path(request.module_path).read_text()
        
        # Build instruction based on refactor type
        if request.refactor_type == "rename":
            intent = f"Rename '{request.target}' to '{request.new_name}'"
        elif request.refactor_type == "extract":
            intent = f"Extract '{request.target}' into a separate function"
        elif request.refactor_type == "inline":
            intent = f"Inline the function/variable '{request.target}'"
        elif request.refactor_type == "move":
            intent = f"Move '{request.target}' to '{request.destination}'"
        else:
            intent = f"Refactor '{request.target}'"
        
        # Delegate to generate-diff
        return await generate_diff(GenerateDiffRequest(
            intent=intent,
            file_path=request.module_path,
            file_content=content,
            constraints=[
                "Update all references",
                "Preserve type safety",
                "Maintain functionality"
            ]
        ))
        
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Module not found: {request.module_path}")
    except Exception as e:
        logger.error("refactor_module_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-impact", response_model=AnalyzeImpactResponse)
async def analyze_impact(request: AnalyzeImpactRequest):
    """
    Analyze the impact of changing a file.
    
    Returns:
    - Blast radius (files, repos, teams affected)
    - Change plan with steps
    - Breaking change detection
    """
    logger.info("analyze_impact_request", file=request.file_path)
    
    try:
        compiler = get_compiler()
        planner = get_planner()
        
        # Compile context
        context = await compiler.compile(
            intent=f"Analyze impact of {request.change_type} on this file",
            primary_file_path=request.file_path,
            workspace_path="."  # TODO: Get from request
        )
        
        # Create plan
        plan = planner.plan(context)
        
        return AnalyzeImpactResponse(
            blast_radius=plan.blast_radius,
            affected_files=[context.primary_file.path] + [f.path for f in context.related_files],
            affected_teams=plan.affected_teams,
            breaking_change=plan.breaking_change,
            change_plan=plan.to_dict()
        )
        
    except Exception as e:
        logger.error("analyze_impact_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Helper Functions
# ============================================================================

def _detect_language(path: str) -> str:
    """Detect language from file extension."""
    ext_map = {
        ".ts": "typescript", ".tsx": "typescript",
        ".js": "javascript", ".jsx": "javascript",
        ".py": "python", ".go": "go", ".rs": "rust"
    }
    from pathlib import Path
    return ext_map.get(Path(path).suffix.lower(), "unknown")


def _is_valid_diff(diff: str) -> bool:
    """Check if output is a valid unified diff."""
    lines = diff.strip().split("\n")
    has_header = any(line.startswith("---") for line in lines)
    has_changes = any(line.startswith("+") or line.startswith("-") for line in lines)
    return has_header and has_changes


def _detect_breaking_change(diff: str) -> bool:
    """Detect if diff contains breaking changes."""
    breaking_patterns = [
        "BREAKING CHANGE",
        "removed field",
        "deleted function",
        "removed export",
        "changed signature",
    ]
    diff_lower = diff.lower()
    return any(pattern.lower() in diff_lower for pattern in breaking_patterns)


def _extract_affected_components(diff: str) -> List[str]:
    """Extract component names from diff."""
    import re
    components = set()
    
    # Extract from file paths
    paths = re.findall(r"(?:---|\+\+\+)\s+[ab]/(.+)", diff)
    components.update(paths)
    
    # Extract from class/function definitions
    defs = re.findall(r"(?:class|def|function|interface)\s+(\w+)", diff)
    components.update(defs)
    
    return list(components)
