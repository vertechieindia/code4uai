"""Memories - Long-term agent memory."""

from __future__ import annotations
import uuid
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class MemoryType(str, Enum):
    """Types of memories."""
    INTERACTION = "interaction"     # Past interaction
    CORRECTION = "correction"       # User correction
    PREFERENCE = "preference"       # User preference
    CONTEXT = "context"             # Contextual info
    SKILL = "skill"                 # Learned skill
    RELATIONSHIP = "relationship"   # Code relationships


class MemoryPriority(str, Enum):
    """Memory priority for retrieval."""
    CRITICAL = "critical"   # Always retrieve
    HIGH = "high"           # Retrieve often
    MEDIUM = "medium"       # Retrieve when relevant
    LOW = "low"             # Rarely retrieve


@dataclass
class Memory:
    """A memory stored by the agent."""
    id: str
    tenant_id: str
    user_id: Optional[str] = None
    
    # Content
    type: MemoryType = MemoryType.CONTEXT
    content: str = ""
    summary: str = ""
    
    # Context
    context: Dict[str, Any] = field(default_factory=dict)
    
    # Priority
    priority: MemoryPriority = MemoryPriority.MEDIUM
    
    # Relevance
    tags: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    
    # Usage
    recall_count: int = 0
    last_recalled: Optional[datetime] = None
    
    # Validity
    expires_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    
    # Embedding
    embedding: Optional[List[float]] = None


class MemoryStore:
    """
    Long-term memory store for the agent.
    
    Features:
    - Store interactions and learnings
    - Semantic recall
    - Priority-based retrieval
    - Decay and consolidation
    - User-specific memories
    """
    
    def __init__(self, tenant_id: str = "default"):
        """Initialize memory store.
        
        Args:
            tenant_id: Tenant identifier
        """
        self.tenant_id = tenant_id
        self._memories: Dict[str, Memory] = {}
    
    def remember(
        self,
        content: str,
        type: MemoryType = MemoryType.CONTEXT,
        user_id: Optional[str] = None,
        summary: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        priority: MemoryPriority = MemoryPriority.MEDIUM,
        tags: Optional[List[str]] = None,
    ) -> Memory:
        """Store a new memory.
        
        Args:
            content: Memory content
            type: Type of memory
            user_id: Associated user
            summary: Short summary
            context: Additional context
            priority: Retrieval priority
            tags: Tags for categorization
            
        Returns:
            Created memory
        """
        memory = Memory(
            id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            user_id=user_id,
            type=type,
            content=content,
            summary=summary or content[:100],
            context=context or {},
            priority=priority,
            tags=tags or [],
            keywords=self._extract_keywords(content),
        )
        
        # Generate embedding
        memory.embedding = self._generate_embedding(content)
        
        self._memories[memory.id] = memory
        return memory
    
    def recall(
        self,
        query: str,
        limit: int = 5,
        user_id: Optional[str] = None,
        type: Optional[MemoryType] = None,
        min_priority: Optional[MemoryPriority] = None,
    ) -> List[Memory]:
        """Recall relevant memories.
        
        Args:
            query: What to recall
            limit: Maximum memories to return
            user_id: Filter by user
            type: Filter by type
            min_priority: Minimum priority
            
        Returns:
            Relevant memories
        """
        query_embedding = self._generate_embedding(query)
        
        # Filter memories
        memories = list(self._memories.values())
        
        if user_id:
            memories = [m for m in memories if m.user_id == user_id or m.user_id is None]
        
        if type:
            memories = [m for m in memories if m.type == type]
        
        if min_priority:
            priority_order = [MemoryPriority.CRITICAL, MemoryPriority.HIGH, MemoryPriority.MEDIUM, MemoryPriority.LOW]
            min_idx = priority_order.index(min_priority)
            memories = [m for m in memories if priority_order.index(m.priority) <= min_idx]
        
        # Calculate relevance scores
        scored = []
        for memory in memories:
            if memory.embedding:
                similarity = self._cosine_similarity(query_embedding, memory.embedding)
                
                # Boost by priority
                priority_boost = {
                    MemoryPriority.CRITICAL: 0.3,
                    MemoryPriority.HIGH: 0.2,
                    MemoryPriority.MEDIUM: 0.1,
                    MemoryPriority.LOW: 0.0,
                }
                score = similarity + priority_boost.get(memory.priority, 0)
                
                # Boost by recency
                age_days = (datetime.utcnow() - memory.created_at).days
                recency_boost = max(0, 0.1 - (age_days * 0.001))
                score += recency_boost
                
                scored.append((memory, score))
        
        # Sort by score
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Update recall counts
        results = []
        for memory, _ in scored[:limit]:
            memory.recall_count += 1
            memory.last_recalled = datetime.utcnow()
            results.append(memory)
        
        return results
    
    def forget(self, memory_id: str) -> bool:
        """Forget a memory.
        
        Args:
            memory_id: Memory to forget
            
        Returns:
            True if forgotten
        """
        if memory_id in self._memories:
            del self._memories[memory_id]
            return True
        return False
    
    def update(
        self,
        memory_id: str,
        content: Optional[str] = None,
        priority: Optional[MemoryPriority] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[Memory]:
        """Update a memory.
        
        Args:
            memory_id: Memory to update
            content: New content
            priority: New priority
            tags: New tags
            
        Returns:
            Updated memory or None
        """
        memory = self._memories.get(memory_id)
        if not memory:
            return None
        
        if content:
            memory.content = content
            memory.summary = content[:100]
            memory.keywords = self._extract_keywords(content)
            memory.embedding = self._generate_embedding(content)
        
        if priority:
            memory.priority = priority
        
        if tags is not None:
            memory.tags = tags
        
        memory.updated_at = datetime.utcnow()
        return memory
    
    def get_context_memories(
        self,
        file_path: str,
        intent: str,
        user_id: Optional[str] = None,
    ) -> List[Memory]:
        """Get memories relevant to a context.
        
        Args:
            file_path: Current file
            intent: Current intent
            user_id: Current user
            
        Returns:
            Relevant memories
        """
        # Combine file path and intent for query
        query = f"{file_path} {intent}"
        
        # Get user-specific and global memories
        memories = self.recall(query, limit=10, user_id=user_id)
        
        # Filter by relevance to file
        file_relevant = [
            m for m in memories
            if file_path in m.content or any(file_path in str(v) for v in m.context.values())
        ]
        
        # Combine and dedupe
        all_memories = list(set(file_relevant) | set(memories[:5]))
        
        return all_memories[:10]
    
    def remember_correction(
        self,
        original: str,
        corrected: str,
        user_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Memory:
        """Remember a user correction.
        
        Args:
            original: What the agent did
            corrected: What the user wanted
            user_id: User who corrected
            context: Additional context
            
        Returns:
            Created memory
        """
        content = f"Correction: When asked to '{original}', the user preferred '{corrected}'"
        
        return self.remember(
            content=content,
            type=MemoryType.CORRECTION,
            user_id=user_id,
            context={**(context or {}), "original": original, "corrected": corrected},
            priority=MemoryPriority.HIGH,
            tags=["correction", "learning"],
        )
    
    def remember_preference(
        self,
        preference: str,
        user_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Memory:
        """Remember a user preference.
        
        Args:
            preference: The preference
            user_id: User
            context: Additional context
            
        Returns:
            Created memory
        """
        return self.remember(
            content=preference,
            type=MemoryType.PREFERENCE,
            user_id=user_id,
            context=context,
            priority=MemoryPriority.HIGH,
            tags=["preference"],
        )
    
    def consolidate(self) -> int:
        """Consolidate memories by merging similar ones.
        
        Returns:
            Number of memories consolidated
        """
        # Group by type and find similar memories
        by_type: Dict[MemoryType, List[Memory]] = {}
        for memory in self._memories.values():
            if memory.type not in by_type:
                by_type[memory.type] = []
            by_type[memory.type].append(memory)
        
        consolidated = 0
        
        for type_memories in by_type.values():
            if len(type_memories) < 2:
                continue
            
            # Find similar memories
            for i, m1 in enumerate(type_memories):
                for m2 in type_memories[i+1:]:
                    if m1.embedding and m2.embedding:
                        similarity = self._cosine_similarity(m1.embedding, m2.embedding)
                        if similarity > 0.9:
                            # Merge into m1
                            m1.content = f"{m1.content}\n\nAlso: {m2.content}"
                            m1.recall_count += m2.recall_count
                            m1.tags = list(set(m1.tags) | set(m2.tags))
                            m1.updated_at = datetime.utcnow()
                            m1.embedding = self._generate_embedding(m1.content)
                            
                            # Remove m2
                            self.forget(m2.id)
                            consolidated += 1
        
        return consolidated
    
    def decay(self, days_threshold: int = 30) -> int:
        """Decay old, unused memories.
        
        Args:
            days_threshold: Days since last recall to consider for decay
            
        Returns:
            Number of memories decayed
        """
        now = datetime.utcnow()
        decayed = 0
        
        for memory_id, memory in list(self._memories.items()):
            # Don't decay critical memories
            if memory.priority == MemoryPriority.CRITICAL:
                continue
            
            # Check last recall or creation
            last_used = memory.last_recalled or memory.created_at
            days_since = (now - last_used).days
            
            if days_since > days_threshold:
                if memory.recall_count < 2:
                    # Low usage, old memory - forget it
                    self.forget(memory_id)
                    decayed += 1
                else:
                    # Demote priority
                    if memory.priority == MemoryPriority.HIGH:
                        memory.priority = MemoryPriority.MEDIUM
                    elif memory.priority == MemoryPriority.MEDIUM:
                        memory.priority = MemoryPriority.LOW
        
        return decayed
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text."""
        # Simple keyword extraction
        import re
        words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]+\b', text.lower())
        
        # Remove common words
        stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                     'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                     'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'this', 'that'}
        
        keywords = [w for w in words if w not in stopwords and len(w) > 2]
        
        # Return unique keywords
        return list(set(keywords))[:20]
    
    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text."""
        import hashlib
        hash_val = hashlib.md5(text.encode()).hexdigest()
        return [int(hash_val[i:i+2], 16) / 255.0 for i in range(0, 32, 2)]
    
    def _cosine_similarity(
        self,
        a: List[float],
        b: List[float],
    ) -> float:
        """Calculate cosine similarity."""
        if not a or not b or len(a) != len(b):
            return 0.0
        
        dot_product = sum(x * y for x, y in zip(a, b))
        magnitude_a = sum(x * x for x in a) ** 0.5
        magnitude_b = sum(x * x for x in b) ** 0.5
        
        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0
        
        return dot_product / (magnitude_a * magnitude_b)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        memories = list(self._memories.values())
        
        return {
            "total": len(memories),
            "by_type": {
                t.value: len([m for m in memories if m.type == t])
                for t in MemoryType
            },
            "by_priority": {
                p.value: len([m for m in memories if m.priority == p])
                for p in MemoryPriority
            },
            "total_recalls": sum(m.recall_count for m in memories),
            "avg_recalls": sum(m.recall_count for m in memories) / len(memories) if memories else 0,
        }

