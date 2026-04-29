"""Knowledge Items - Structured knowledge storage."""

from __future__ import annotations
import uuid
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class KnowledgeType(str, Enum):
    """Types of knowledge items."""
    RULE = "rule"               # Coding rule/constraint
    PREFERENCE = "preference"   # User preference
    PATTERN = "pattern"         # Code pattern
    CONTEXT = "context"         # Project context
    FACT = "fact"               # General fact
    DECISION = "decision"       # Past decision
    TEMPLATE = "template"       # Code template
    GLOSSARY = "glossary"       # Term definition


class KnowledgeScope(str, Enum):
    """Scope of knowledge."""
    GLOBAL = "global"           # Applies everywhere
    PROJECT = "project"         # Specific project
    WORKSPACE = "workspace"     # Specific workspace
    FILE = "file"               # Specific file
    DIRECTORY = "directory"     # Specific directory


class KnowledgeSource(str, Enum):
    """Source of knowledge."""
    USER = "user"               # User-defined
    INFERRED = "inferred"       # Inferred from code
    CODEOWNERS = "codeowners"   # From CODEOWNERS file
    CONFIG = "config"           # From config files
    DOCUMENTATION = "documentation"  # From docs
    AGENT = "agent"             # Learned by agent


@dataclass
class KnowledgeItem:
    """A piece of knowledge."""
    id: str
    tenant_id: str
    
    # Content
    type: KnowledgeType
    title: str
    content: str
    
    # Scope
    scope: KnowledgeScope = KnowledgeScope.GLOBAL
    scope_path: Optional[str] = None  # Path for FILE/DIRECTORY scope
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    priority: int = 0  # Higher = more important
    
    # Source
    source: KnowledgeSource = KnowledgeSource.USER
    source_ref: Optional[str] = None  # Reference to source
    
    # Usage
    usage_count: int = 0
    last_used: Optional[datetime] = None
    
    # Validity
    enabled: bool = True
    expires_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    
    # Creator
    created_by: Optional[str] = None
    
    # Embedding
    embedding: Optional[List[float]] = None


class KnowledgeStore:
    """
    Store for knowledge items.
    
    Features:
    - CRUD operations
    - Semantic search
    - Scope-based filtering
    - Usage tracking
    - Embedding-based retrieval
    """
    
    def __init__(self, tenant_id: str = "default"):
        """Initialize knowledge store.
        
        Args:
            tenant_id: Tenant identifier
        """
        self.tenant_id = tenant_id
        self._items: Dict[str, KnowledgeItem] = {}
        self._embeddings: Dict[str, List[float]] = {}
    
    def create(
        self,
        type: KnowledgeType,
        title: str,
        content: str,
        scope: KnowledgeScope = KnowledgeScope.GLOBAL,
        scope_path: Optional[str] = None,
        tags: Optional[List[str]] = None,
        priority: int = 0,
        source: KnowledgeSource = KnowledgeSource.USER,
        created_by: Optional[str] = None,
    ) -> KnowledgeItem:
        """Create a knowledge item.
        
        Args:
            type: Knowledge type
            title: Title
            content: Content
            scope: Scope of application
            scope_path: Path for scoped items
            tags: Tags for categorization
            priority: Priority (higher = more important)
            source: Source of knowledge
            created_by: User who created
            
        Returns:
            Created item
        """
        item = KnowledgeItem(
            id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            type=type,
            title=title,
            content=content,
            scope=scope,
            scope_path=scope_path,
            tags=tags or [],
            priority=priority,
            source=source,
            created_by=created_by,
        )
        
        self._items[item.id] = item
        
        # Generate embedding
        item.embedding = self._generate_embedding(f"{title} {content}")
        
        return item
    
    def get(self, item_id: str) -> Optional[KnowledgeItem]:
        """Get a knowledge item."""
        return self._items.get(item_id)
    
    def update(
        self,
        item_id: str,
        **updates,
    ) -> Optional[KnowledgeItem]:
        """Update a knowledge item."""
        item = self._items.get(item_id)
        if not item:
            return None
        
        for key, value in updates.items():
            if hasattr(item, key):
                setattr(item, key, value)
        
        item.updated_at = datetime.utcnow()
        
        # Regenerate embedding if content changed
        if "title" in updates or "content" in updates:
            item.embedding = self._generate_embedding(f"{item.title} {item.content}")
        
        return item
    
    def delete(self, item_id: str) -> bool:
        """Delete a knowledge item."""
        if item_id in self._items:
            del self._items[item_id]
            return True
        return False
    
    def list(
        self,
        type: Optional[KnowledgeType] = None,
        scope: Optional[KnowledgeScope] = None,
        scope_path: Optional[str] = None,
        tags: Optional[List[str]] = None,
        enabled_only: bool = True,
    ) -> List[KnowledgeItem]:
        """List knowledge items with filtering.
        
        Args:
            type: Filter by type
            scope: Filter by scope
            scope_path: Filter by scope path
            tags: Filter by tags (any match)
            enabled_only: Only enabled items
            
        Returns:
            Matching items
        """
        items = list(self._items.values())
        
        if enabled_only:
            items = [i for i in items if i.enabled]
        
        if type:
            items = [i for i in items if i.type == type]
        
        if scope:
            items = [i for i in items if i.scope == scope]
        
        if scope_path:
            items = [i for i in items if i.scope_path == scope_path or i.scope == KnowledgeScope.GLOBAL]
        
        if tags:
            items = [i for i in items if any(t in i.tags for t in tags)]
        
        return sorted(items, key=lambda i: i.priority, reverse=True)
    
    def search(
        self,
        query: str,
        limit: int = 10,
        scope_path: Optional[str] = None,
    ) -> List[KnowledgeItem]:
        """Semantic search for knowledge items.
        
        Args:
            query: Search query
            limit: Maximum results
            scope_path: Scope to search within
            
        Returns:
            Matching items sorted by relevance
        """
        query_embedding = self._generate_embedding(query)
        
        items = self.list(scope_path=scope_path)
        
        # Calculate similarities
        scored_items = []
        for item in items:
            if item.embedding:
                similarity = self._cosine_similarity(query_embedding, item.embedding)
                scored_items.append((item, similarity))
        
        # Sort by similarity
        scored_items.sort(key=lambda x: x[1], reverse=True)
        
        return [item for item, _ in scored_items[:limit]]
    
    def get_for_context(
        self,
        file_path: str,
        intent: Optional[str] = None,
    ) -> List[KnowledgeItem]:
        """Get relevant knowledge for a context.
        
        Args:
            file_path: Current file path
            intent: Optional intent for filtering
            
        Returns:
            Relevant knowledge items
        """
        items = []
        
        # Get global items
        global_items = self.list(scope=KnowledgeScope.GLOBAL)
        items.extend(global_items)
        
        # Get file-specific items
        file_items = self.list(scope=KnowledgeScope.FILE, scope_path=file_path)
        items.extend(file_items)
        
        # Get directory items
        import os
        dir_path = os.path.dirname(file_path)
        dir_items = self.list(scope=KnowledgeScope.DIRECTORY, scope_path=dir_path)
        items.extend(dir_items)
        
        # If intent provided, filter by relevance
        if intent:
            intent_items = self.search(intent, limit=5)
            items = list(set(items) | set(intent_items))
        
        # Sort by priority and usage
        items.sort(key=lambda i: (i.priority, i.usage_count), reverse=True)
        
        return items[:20]
    
    def record_usage(self, item_id: str) -> None:
        """Record that an item was used."""
        item = self._items.get(item_id)
        if item:
            item.usage_count += 1
            item.last_used = datetime.utcnow()
    
    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text.
        
        In production, this would use:
        - OpenAI embeddings
        - Local embedding model
        - SentenceTransformers
        """
        # Mock embedding - in production use real embeddings
        import hashlib
        hash_val = hashlib.md5(text.encode()).hexdigest()
        return [int(hash_val[i:i+2], 16) / 255.0 for i in range(0, 32, 2)]
    
    def _cosine_similarity(
        self,
        a: List[float],
        b: List[float],
    ) -> float:
        """Calculate cosine similarity between two vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0
        
        dot_product = sum(x * y for x, y in zip(a, b))
        magnitude_a = sum(x * x for x in a) ** 0.5
        magnitude_b = sum(x * x for x in b) ** 0.5
        
        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0
        
        return dot_product / (magnitude_a * magnitude_b)
    
    def export(self) -> List[Dict[str, Any]]:
        """Export all knowledge items."""
        return [
            {
                "id": item.id,
                "type": item.type.value,
                "title": item.title,
                "content": item.content,
                "scope": item.scope.value,
                "scope_path": item.scope_path,
                "tags": item.tags,
                "priority": item.priority,
            }
            for item in self._items.values()
        ]
    
    def import_items(self, items: List[Dict[str, Any]]) -> int:
        """Import knowledge items."""
        count = 0
        for data in items:
            self.create(
                type=KnowledgeType(data.get("type", "fact")),
                title=data.get("title", ""),
                content=data.get("content", ""),
                scope=KnowledgeScope(data.get("scope", "global")),
                scope_path=data.get("scope_path"),
                tags=data.get("tags", []),
                priority=data.get("priority", 0),
            )
            count += 1
        return count

