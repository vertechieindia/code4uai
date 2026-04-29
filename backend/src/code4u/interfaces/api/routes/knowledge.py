"""API routes for Knowledge Items & Memories."""

from __future__ import annotations
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from code4u.code_intelligence.knowledge import KnowledgeStore, MemoryStore, ContextBuilder
from code4u.code_intelligence.knowledge.items import KnowledgeType, KnowledgeScope
from code4u.code_intelligence.knowledge.memories import MemoryType, MemoryPriority


router = APIRouter(prefix="/knowledge", tags=["knowledge"])

# Instances
_knowledge_stores: Dict[str, KnowledgeStore] = {}
_memory_stores: Dict[str, MemoryStore] = {}
_context_builders: Dict[str, ContextBuilder] = {}


def get_stores(tenant_id: str):
    if tenant_id not in _knowledge_stores:
        _knowledge_stores[tenant_id] = KnowledgeStore(tenant_id)
        _memory_stores[tenant_id] = MemoryStore(tenant_id)
        _context_builders[tenant_id] = ContextBuilder(
            _knowledge_stores[tenant_id],
            _memory_stores[tenant_id],
        )
    return _knowledge_stores[tenant_id], _memory_stores[tenant_id], _context_builders[tenant_id]


# ============= Request/Response Models =============

class CreateKnowledgeRequest(BaseModel):
    """Request to create knowledge item."""
    type: str = "fact"
    title: str
    content: str
    scope: str = "global"
    scope_path: Optional[str] = None
    tags: List[str] = []
    priority: int = 0


class KnowledgeItem(BaseModel):
    """Knowledge item."""
    id: str
    type: str
    title: str
    content: str
    scope: str
    tags: List[str]
    priority: int
    usage_count: int


class CreateMemoryRequest(BaseModel):
    """Request to create memory."""
    content: str
    type: str = "context"
    summary: Optional[str] = None
    priority: str = "medium"
    tags: List[str] = []


class MemoryItem(BaseModel):
    """Memory item."""
    id: str
    type: str
    content: str
    summary: str
    priority: str
    recall_count: int


class CorrectionRequest(BaseModel):
    """Request to record a correction."""
    original: str
    corrected: str


class ContextRequest(BaseModel):
    """Request to build context."""
    file_path: str
    intent: str


class ContextResponse(BaseModel):
    """Built context response."""
    rules: List[Dict[str, str]]
    preferences: List[Dict[str, str]]
    patterns: List[Dict[str, str]]
    corrections: List[Dict[str, str]]
    summary: str
    prompt: str


# ============= Knowledge Endpoints =============

@router.post("/items", response_model=KnowledgeItem)
async def create_knowledge(
    request: CreateKnowledgeRequest,
    x_tenant_id: str = Header(default="default"),
    x_user_id: str = Header(default=None),
) -> KnowledgeItem:
    """Create a knowledge item."""
    knowledge, _, _ = get_stores(x_tenant_id)
    
    item = knowledge.create(
        type=KnowledgeType(request.type),
        title=request.title,
        content=request.content,
        scope=KnowledgeScope(request.scope),
        scope_path=request.scope_path,
        tags=request.tags,
        priority=request.priority,
        created_by=x_user_id,
    )
    
    return KnowledgeItem(
        id=item.id,
        type=item.type.value,
        title=item.title,
        content=item.content,
        scope=item.scope.value,
        tags=item.tags,
        priority=item.priority,
        usage_count=item.usage_count,
    )


@router.get("/items", response_model=List[KnowledgeItem])
async def list_knowledge(
    type: Optional[str] = None,
    scope: Optional[str] = None,
    tags: Optional[str] = None,
    x_tenant_id: str = Header(default="default"),
) -> List[KnowledgeItem]:
    """List knowledge items."""
    knowledge, _, _ = get_stores(x_tenant_id)
    
    items = knowledge.list(
        type=KnowledgeType(type) if type else None,
        scope=KnowledgeScope(scope) if scope else None,
        tags=tags.split(",") if tags else None,
    )
    
    return [
        KnowledgeItem(
            id=item.id,
            type=item.type.value,
            title=item.title,
            content=item.content,
            scope=item.scope.value,
            tags=item.tags,
            priority=item.priority,
            usage_count=item.usage_count,
        )
        for item in items
    ]


@router.get("/items/{item_id}", response_model=KnowledgeItem)
async def get_knowledge(
    item_id: str,
    x_tenant_id: str = Header(default="default"),
) -> KnowledgeItem:
    """Get a knowledge item."""
    knowledge, _, _ = get_stores(x_tenant_id)
    item = knowledge.get(item_id)
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    return KnowledgeItem(
        id=item.id,
        type=item.type.value,
        title=item.title,
        content=item.content,
        scope=item.scope.value,
        tags=item.tags,
        priority=item.priority,
        usage_count=item.usage_count,
    )


@router.put("/items/{item_id}", response_model=KnowledgeItem)
async def update_knowledge(
    item_id: str,
    request: CreateKnowledgeRequest,
    x_tenant_id: str = Header(default="default"),
) -> KnowledgeItem:
    """Update a knowledge item."""
    knowledge, _, _ = get_stores(x_tenant_id)
    
    item = knowledge.update(
        item_id,
        title=request.title,
        content=request.content,
        tags=request.tags,
        priority=request.priority,
    )
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    return KnowledgeItem(
        id=item.id,
        type=item.type.value,
        title=item.title,
        content=item.content,
        scope=item.scope.value,
        tags=item.tags,
        priority=item.priority,
        usage_count=item.usage_count,
    )


@router.delete("/items/{item_id}")
async def delete_knowledge(
    item_id: str,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, bool]:
    """Delete a knowledge item."""
    knowledge, _, _ = get_stores(x_tenant_id)
    result = knowledge.delete(item_id)
    return {"deleted": result}


@router.get("/items/search")
async def search_knowledge(
    query: str,
    limit: int = 10,
    x_tenant_id: str = Header(default="default"),
) -> List[KnowledgeItem]:
    """Search knowledge items."""
    knowledge, _, _ = get_stores(x_tenant_id)
    items = knowledge.search(query, limit=limit)
    
    return [
        KnowledgeItem(
            id=item.id,
            type=item.type.value,
            title=item.title,
            content=item.content,
            scope=item.scope.value,
            tags=item.tags,
            priority=item.priority,
            usage_count=item.usage_count,
        )
        for item in items
    ]


# ============= Memory Endpoints =============

@router.post("/memories", response_model=MemoryItem)
async def create_memory(
    request: CreateMemoryRequest,
    x_tenant_id: str = Header(default="default"),
    x_user_id: str = Header(default=None),
) -> MemoryItem:
    """Create a memory."""
    _, memories, _ = get_stores(x_tenant_id)
    
    memory = memories.remember(
        content=request.content,
        type=MemoryType(request.type),
        user_id=x_user_id,
        summary=request.summary,
        priority=MemoryPriority(request.priority),
        tags=request.tags,
    )
    
    return MemoryItem(
        id=memory.id,
        type=memory.type.value,
        content=memory.content,
        summary=memory.summary,
        priority=memory.priority.value,
        recall_count=memory.recall_count,
    )


@router.get("/memories/recall")
async def recall_memories(
    query: str,
    limit: int = 5,
    type: Optional[str] = None,
    x_tenant_id: str = Header(default="default"),
    x_user_id: str = Header(default=None),
) -> List[MemoryItem]:
    """Recall relevant memories."""
    _, memories, _ = get_stores(x_tenant_id)
    
    results = memories.recall(
        query=query,
        limit=limit,
        user_id=x_user_id,
        type=MemoryType(type) if type else None,
    )
    
    return [
        MemoryItem(
            id=m.id,
            type=m.type.value,
            content=m.content,
            summary=m.summary,
            priority=m.priority.value,
            recall_count=m.recall_count,
        )
        for m in results
    ]


@router.post("/memories/correction")
async def record_correction(
    request: CorrectionRequest,
    x_tenant_id: str = Header(default="default"),
    x_user_id: str = Header(default=None),
) -> MemoryItem:
    """Record a user correction."""
    _, memories, _ = get_stores(x_tenant_id)
    
    memory = memories.remember_correction(
        original=request.original,
        corrected=request.corrected,
        user_id=x_user_id,
    )
    
    return MemoryItem(
        id=memory.id,
        type=memory.type.value,
        content=memory.content,
        summary=memory.summary,
        priority=memory.priority.value,
        recall_count=memory.recall_count,
    )


@router.delete("/memories/{memory_id}")
async def forget_memory(
    memory_id: str,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, bool]:
    """Forget a memory."""
    _, memories, _ = get_stores(x_tenant_id)
    result = memories.forget(memory_id)
    return {"forgotten": result}


@router.post("/memories/consolidate")
async def consolidate_memories(
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, int]:
    """Consolidate similar memories."""
    _, memories, _ = get_stores(x_tenant_id)
    count = memories.consolidate()
    return {"consolidated": count}


@router.get("/memories/stats")
async def get_memory_stats(
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, Any]:
    """Get memory statistics."""
    _, memories, _ = get_stores(x_tenant_id)
    return memories.get_stats()


# ============= Context Endpoints =============

@router.post("/context/build", response_model=ContextResponse)
async def build_context(
    request: ContextRequest,
    x_tenant_id: str = Header(default="default"),
    x_user_id: str = Header(default=None),
) -> ContextResponse:
    """Build context for a request."""
    _, _, context_builder = get_stores(x_tenant_id)
    
    context = context_builder.build(
        file_path=request.file_path,
        intent=request.intent,
        user_id=x_user_id,
    )
    
    return ContextResponse(
        rules=context.rules,
        preferences=context.preferences,
        patterns=context.patterns,
        corrections=context.corrections,
        summary=context.summary,
        prompt=context.to_prompt(),
    )


@router.get("/context/search")
async def search_context(
    query: str,
    limit: int = 10,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, List[Any]]:
    """Search across knowledge and memories."""
    _, _, context_builder = get_stores(x_tenant_id)
    return context_builder.search(query, limit=limit)


@router.get("/stats")
async def get_all_stats(
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, Any]:
    """Get all knowledge/memory statistics."""
    _, _, context_builder = get_stores(x_tenant_id)
    return context_builder.get_stats()

