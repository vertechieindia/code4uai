"""API routes for Model Picker & Routing."""

from __future__ import annotations
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from code4u.ai_engine.model_picker import (
    ModelRegistry,
    ModelRouter,
    ModelPicker,
    ModelProvider,
    RoutingStrategy,
    ModelCapability,
)
from code4u.ai_engine.model_picker.router import RoutingContext


router = APIRouter(prefix="/models", tags=["models"])

# Shared instances
_registry = ModelRegistry()
_router = ModelRouter(_registry)
_picker = ModelPicker(_registry)


# ============= Request/Response Models =============

class ModelInfo(BaseModel):
    """Model information for API response."""
    id: str
    name: str
    provider: str
    capabilities: List[str]
    max_context_tokens: int
    quality_score: float
    cost_per_million_input: float
    cost_per_million_output: float
    is_available: bool
    tags: List[str]


class RouteRequest(BaseModel):
    """Request for model routing."""
    task_type: str
    complexity_score: float = 0.5
    estimated_input_tokens: int = 1000
    estimated_output_tokens: int = 500
    required_capabilities: List[str] = []
    preferred_model_id: Optional[str] = None


class RouteResponse(BaseModel):
    """Response from model routing."""
    model_id: str
    model_name: str
    reason: str
    strategy_used: str
    estimated_cost: float
    alternatives: List[str]


class UsageStats(BaseModel):
    """Model usage statistics."""
    model_id: str
    total_requests: int
    success_rate: float
    total_tokens: int
    total_cost: float
    avg_latency_ms: float


# ============= Endpoints =============

@router.get("/", response_model=List[ModelInfo])
async def list_models(
    provider: Optional[str] = None,
    capability: Optional[str] = None,
    x_tenant_id: str = Header(default="default"),
) -> List[ModelInfo]:
    """List available models."""
    if provider:
        models = _registry.list_by_provider(ModelProvider(provider))
    elif capability:
        models = _registry.list_by_capability(ModelCapability(capability))
    else:
        models = _registry.list_for_tenant(x_tenant_id)
    
    return [
        ModelInfo(
            id=m.id,
            name=m.name,
            provider=m.provider.value,
            capabilities=[c.value for c in m.capabilities],
            max_context_tokens=m.max_context_tokens,
            quality_score=m.code_quality_score,
            cost_per_million_input=m.input_cost_per_million,
            cost_per_million_output=m.output_cost_per_million,
            is_available=m.is_available,
            tags=m.tags,
        )
        for m in models
    ]


@router.get("/routing-table")
async def get_routing_table() -> Dict[str, Any]:
    """Return the full MODEL_ROUTING_TABLE for inspection."""
    from code4u.ai_engine.llm.smart_router import MODEL_ROUTING_TABLE
    return {"routingTable": MODEL_ROUTING_TABLE}


@router.get("/{model_id}", response_model=ModelInfo)
async def get_model(
    model_id: str,
) -> ModelInfo:
    """Get model by ID."""
    model = _registry.get(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    return ModelInfo(
        id=model.id,
        name=model.name,
        provider=model.provider.value,
        capabilities=[c.value for c in model.capabilities],
        max_context_tokens=model.max_context_tokens,
        quality_score=model.code_quality_score,
        cost_per_million_input=model.input_cost_per_million,
        cost_per_million_output=model.output_cost_per_million,
        is_available=model.is_available,
        tags=model.tags,
    )


@router.post("/route", response_model=RouteResponse)
async def route_to_model(
    request: RouteRequest,
    x_tenant_id: str = Header(default="default"),
) -> RouteResponse:
    """Route a request to the best model."""
    context = RoutingContext(
        task_type=request.task_type,
        complexity_score=request.complexity_score,
        estimated_input_tokens=request.estimated_input_tokens,
        estimated_output_tokens=request.estimated_output_tokens,
        tenant_id=x_tenant_id,
        preferred_model_id=request.preferred_model_id,
    )
    
    # Add required capabilities
    for cap in request.required_capabilities:
        try:
            context.required_capabilities.add(ModelCapability(cap))
        except ValueError:
            pass
    
    try:
        selection = _router.route(context)
        
        return RouteResponse(
            model_id=selection.model.id,
            model_name=selection.model.name,
            reason=selection.reason,
            strategy_used=selection.strategy_used.value,
            estimated_cost=selection.estimated_cost,
            alternatives=[m.id for m in selection.alternatives],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/picker/options")
async def get_picker_options(
    task_type: Optional[str] = None,
    x_tenant_id: str = Header(default="default"),
) -> List[Dict[str, Any]]:
    """Get model options for picker UI."""
    options = _picker.get_options(x_tenant_id, task_type)
    
    return [
        {
            "id": o.id,
            "name": o.name,
            "provider": o.provider,
            "description": o.description,
            "icon": o.icon,
            "badge": o.badge,
            "capabilities": o.capabilities,
            "quality_score": o.quality_score,
            "speed_score": o.speed_score,
            "cost_per_request": o.cost_per_request,
            "is_available": o.is_available,
            "is_premium": o.is_premium,
        }
        for o in options
    ]


@router.get("/picker/suggested")
async def get_suggested_model(
    task_type: str,
    complexity: float = 0.5,
    code_length: int = 1000,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, Any]:
    """Get suggested model for a task."""
    option = _picker.get_suggested_model(
        tenant_id=x_tenant_id,
        task_type=task_type,
        complexity=complexity,
        code_length=code_length,
    )
    
    return {
        "id": option.id,
        "name": option.name,
        "reason": option.description,
        "cost_estimate": option.cost_per_request,
    }


@router.get("/strategies")
async def get_routing_strategies() -> List[Dict[str, Any]]:
    """Get available routing strategies."""
    return _picker.get_routing_strategies()


@router.get("/usage")
async def get_usage_stats(
    model_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Get model usage statistics."""
    return _picker.get_usage_stats(model_id)


@router.post("/{model_id}/availability")
async def set_model_availability(
    model_id: str,
    available: bool,
) -> Dict[str, str]:
    """Set model availability."""
    if _registry.set_availability(model_id, available):
        return {"status": "updated", "model_id": model_id, "available": str(available)}
    raise HTTPException(status_code=404, detail="Model not found")


# ============= Dynamic Routing =============

class SmartRouteRequest(BaseModel):
    agentType: str
    intent: str = ""
    airGapped: bool = False


@router.post("/smart-route")
async def smart_route(request: SmartRouteRequest) -> Dict[str, Any]:
    """Use the MODEL_ROUTING_TABLE to pick the best model for an agent type.

    Returns the recommended model, complexity estimate, and whether
    a local or cloud provider will be used.
    """
    from code4u.ai_engine.llm.smart_router import (
        get_model_for_agent,
        classify_complexity,
        MODEL_ROUTING_TABLE,
    )
    from code4u.agents.orchestrator.chief import ChiefArchitect

    chief = ChiefArchitect()
    complexity = chief.estimate_complexity(request.intent) if request.intent else "low"
    model = get_model_for_agent(request.agentType, air_gapped=request.airGapped)
    mode = "local" if request.airGapped else "cloud"
    routing_entry = MODEL_ROUTING_TABLE.get(request.agentType.lower(), {})

    return {
        "agentType": request.agentType,
        "complexity": complexity,
        "mode": mode,
        "model": model,
        "routingTable": routing_entry,
        "airGapped": request.airGapped,
    }

