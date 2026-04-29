"""API routes for Rules & Workflows Engine."""

from __future__ import annotations
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from code4u.platform_core.rules_engine import (
    RulesEngine,
    Rule,
    RuleType,
    RuleScope,
    Workflow,
    Memory,
)
from code4u.platform_core.rules_engine.models import RulesContext


router = APIRouter(prefix="/rules", tags=["rules"])

# Tenant engines
_engines: Dict[str, RulesEngine] = {}


def get_engine(tenant_id: str) -> RulesEngine:
    """Get or create engine for tenant."""
    if tenant_id not in _engines:
        _engines[tenant_id] = RulesEngine(tenant_id=tenant_id)
    return _engines[tenant_id]


# ============= Request/Response Models =============

class RuleCreate(BaseModel):
    """Request to create a rule."""
    name: str
    type: str
    instruction: str
    scope: str = "global"
    globs: List[str] = []
    languages: List[str] = []
    priority: int = 0
    description: Optional[str] = None


class RuleResponse(BaseModel):
    """Rule response."""
    id: str
    name: str
    type: str
    instruction: str
    scope: str
    globs: List[str]
    priority: int
    enabled: bool


class WorkflowCreate(BaseModel):
    """Request to create a workflow."""
    name: str
    command: str
    description: str = ""
    steps: List[Dict[str, Any]] = []
    input_variables: List[str] = []


class WorkflowResponse(BaseModel):
    """Workflow response."""
    id: str
    name: str
    command: str
    description: str
    steps: List[Dict[str, Any]]
    tags: List[str]
    enabled: bool


class MemoryCreate(BaseModel):
    """Request to create a memory."""
    content: str
    type: str = "preference"


class MemoryResponse(BaseModel):
    """Memory response."""
    id: str
    content: str
    type: str
    confidence: float
    use_count: int
    enabled: bool


class ApplyRulesRequest(BaseModel):
    """Request to apply rules to context."""
    file_path: Optional[str] = None
    language: Optional[str] = None
    directory: Optional[str] = None


# ============= Rules Endpoints =============

@router.get("/", response_model=List[RuleResponse])
async def list_rules(
    x_tenant_id: str = Header(default="default"),
) -> List[RuleResponse]:
    """List all rules for tenant."""
    engine = get_engine(x_tenant_id)
    
    return [
        RuleResponse(
            id=r.id,
            name=r.name,
            type=r.type.value,
            instruction=r.instruction,
            scope=r.scope.value,
            globs=r.globs,
            priority=r.priority,
            enabled=r.enabled,
        )
        for r in engine.list_rules()
    ]


@router.post("/", response_model=RuleResponse)
async def create_rule(
    request: RuleCreate,
    x_tenant_id: str = Header(default="default"),
) -> RuleResponse:
    """Create a new rule."""
    engine = get_engine(x_tenant_id)
    
    import uuid
    rule = Rule(
        id=str(uuid.uuid4()),
        name=request.name,
        type=RuleType(request.type),
        instruction=request.instruction,
        scope=RuleScope(request.scope),
        globs=request.globs,
        languages=request.languages,
        priority=request.priority,
        description=request.description,
    )
    
    engine.add_rule(rule)
    
    return RuleResponse(
        id=rule.id,
        name=rule.name,
        type=rule.type.value,
        instruction=rule.instruction,
        scope=rule.scope.value,
        globs=rule.globs,
        priority=rule.priority,
        enabled=rule.enabled,
    )


@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: str,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, str]:
    """Delete a rule."""
    engine = get_engine(x_tenant_id)
    
    if engine.remove_rule(rule_id):
        return {"status": "deleted", "rule_id": rule_id}
    raise HTTPException(status_code=404, detail="Rule not found")


@router.post("/apply")
async def apply_rules(
    request: ApplyRulesRequest,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, Any]:
    """Apply rules to get prompt additions."""
    engine = get_engine(x_tenant_id)
    
    context = RulesContext(
        file_path=request.file_path,
        language=request.language,
        directory=request.directory,
    )
    
    applicable = engine.get_applicable_rules(context)
    prompt_additions = engine.build_prompt_additions(context)
    
    return {
        "applicable_rules": len(applicable),
        "rule_ids": [r.id for r in applicable],
        "prompt_additions": prompt_additions,
    }


# ============= Workflows Endpoints =============

@router.get("/workflows", response_model=List[WorkflowResponse])
async def list_workflows(
    x_tenant_id: str = Header(default="default"),
) -> List[WorkflowResponse]:
    """List all workflows."""
    engine = get_engine(x_tenant_id)
    
    return [
        WorkflowResponse(
            id=w.id,
            name=w.name,
            command=w.command,
            description=w.description,
            steps=[
                {"id": s.id, "name": s.name, "action": s.action}
                for s in w.steps
            ],
            tags=w.tags,
            enabled=w.enabled,
        )
        for w in engine.list_workflows()
    ]


@router.get("/workflows/{command}")
async def get_workflow_by_command(
    command: str,
    x_tenant_id: str = Header(default="default"),
) -> WorkflowResponse:
    """Get workflow by command name."""
    engine = get_engine(x_tenant_id)
    workflow = engine.get_workflow_by_command(command)
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    return WorkflowResponse(
        id=workflow.id,
        name=workflow.name,
        command=workflow.command,
        description=workflow.description,
        steps=[
            {"id": s.id, "name": s.name, "action": s.action, "prompt": s.prompt}
            for s in workflow.steps
        ],
        tags=workflow.tags,
        enabled=workflow.enabled,
    )


@router.post("/workflows/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: str,
    variables: Dict[str, Any] = {},
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, Any]:
    """Execute a workflow."""
    engine = get_engine(x_tenant_id)
    
    context = RulesContext()
    
    try:
        result = await engine.execute_workflow(workflow_id, context, variables)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ============= Memories Endpoints =============

@router.get("/memories", response_model=List[MemoryResponse])
async def list_memories(
    x_tenant_id: str = Header(default="default"),
) -> List[MemoryResponse]:
    """List all memories."""
    engine = get_engine(x_tenant_id)
    
    return [
        MemoryResponse(
            id=m.id,
            content=m.content,
            type=m.type,
            confidence=m.confidence,
            use_count=m.use_count,
            enabled=m.enabled,
        )
        for m in engine.list_memories()
    ]


@router.post("/memories", response_model=MemoryResponse)
async def create_memory(
    request: MemoryCreate,
    x_tenant_id: str = Header(default="default"),
) -> MemoryResponse:
    """Create a new memory."""
    engine = get_engine(x_tenant_id)
    
    memory = engine.create_memory_from_interaction(
        content=request.content,
        source="user",
    )
    
    return MemoryResponse(
        id=memory.id,
        content=memory.content,
        type=memory.type,
        confidence=memory.confidence,
        use_count=memory.use_count,
        enabled=memory.enabled,
    )


@router.delete("/memories/{memory_id}")
async def delete_memory(
    memory_id: str,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, str]:
    """Delete a memory."""
    engine = get_engine(x_tenant_id)
    
    if engine.remove_memory(memory_id):
        return {"status": "deleted", "memory_id": memory_id}
    raise HTTPException(status_code=404, detail="Memory not found")

