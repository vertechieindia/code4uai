"""Model Distillation API — fine-tuning data management.

Endpoints:
  - ``GET  /distill/stats``        — training data statistics
  - ``GET  /distill/examples``     — list collected training examples
  - ``POST /distill/collect``      — pull from telemetry into distillation store
  - ``POST /distill/export``       — export JSONL for fine-tuning
  - ``GET  /distill/export-data``  — download training data as JSON
  - ``POST /distill/clear``        — clear all collected data
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel, Field

from code4u.ai_engine.distillation import get_distillation_store, TrainingExample

router = APIRouter()


class AddExampleRequest(BaseModel):
    agentType: str = Field("", description="Agent type that produced the output.")
    modelUsed: str = Field("gpt-4o-mini", description="Model that generated the response.")
    complexity: str = Field("low", description="Task complexity: low | medium | high.")
    systemPrompt: str = Field("", description="System prompt used.")
    userInput: str = Field(..., description="User input / goal.")
    assistantOutput: str = Field(..., description="Assistant-generated output.")
    goal: str = Field("", description="Original goal.")


@router.get("/distill/stats")
async def distillation_stats() -> Dict[str, Any]:
    """Return statistics about collected training data."""
    store = get_distillation_store()
    return store.stats()


@router.get("/distill/examples")
async def distillation_examples(
    limit: int = 50,
    agent_type: str = "",
) -> Dict[str, Any]:
    """List collected training examples."""
    store = get_distillation_store()
    examples = store.get_examples(limit=limit, agent_type=agent_type)
    return {
        "count": len(examples),
        "examples": [
            {
                "id": e.id,
                "agentType": e.agent_type,
                "modelUsed": e.model_used,
                "complexity": e.complexity,
                "goal": e.goal[:100],
                "inputPreview": e.user_input[:150],
                "outputPreview": e.assistant_output[:150],
                "timestamp": e.timestamp,
            }
            for e in examples
        ],
    }


@router.post("/distill/add")
async def add_example(request: AddExampleRequest) -> Dict[str, str]:
    """Manually add a training example."""
    store = get_distillation_store()
    store.add(TrainingExample(
        agent_type=request.agentType,
        model_used=request.modelUsed,
        complexity=request.complexity,
        system_prompt=request.systemPrompt,
        user_input=request.userInput,
        assistant_output=request.assistantOutput,
        goal=request.goal or request.userInput[:80],
    ))
    return {"status": "added", "totalExamples": str(store.count)}


@router.post("/distill/collect")
async def collect_from_telemetry() -> Dict[str, Any]:
    """Pull successful executions from TelemetryStore into distillation data."""
    store = get_distillation_store()
    added = store.collect_from_telemetry()
    return {
        "status": "collected",
        "newExamples": added,
        "totalExamples": store.count,
    }


@router.post("/distill/export")
async def export_jsonl() -> Dict[str, Any]:
    """Export training data to JSONL file on disk."""
    store = get_distillation_store()
    path = store.export_jsonl()
    return {
        "status": "exported",
        "path": path,
        "totalExamples": store.count,
    }


@router.get("/distill/export-data")
async def export_data() -> Dict[str, Any]:
    """Download training data as JSON (chat format)."""
    store = get_distillation_store()
    return {
        "format": "chat",
        "data": store.export_chat_format(),
        "count": store.count,
    }


@router.post("/distill/clear")
async def clear_distillation() -> Dict[str, str]:
    """Clear all collected training data."""
    store = get_distillation_store()
    store.clear()
    return {"status": "cleared"}
