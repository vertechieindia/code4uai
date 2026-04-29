"""Context Builder - Build context from knowledge and memories."""

from __future__ import annotations
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from .items import KnowledgeStore, KnowledgeItem, KnowledgeType
from .memories import MemoryStore, Memory, MemoryType


@dataclass
class BuiltContext:
    """Built context for the agent."""
    # Knowledge items
    rules: List[Dict[str, str]] = field(default_factory=list)
    preferences: List[Dict[str, str]] = field(default_factory=list)
    patterns: List[Dict[str, str]] = field(default_factory=list)
    facts: List[Dict[str, str]] = field(default_factory=list)
    
    # Memories
    corrections: List[Dict[str, str]] = field(default_factory=list)
    past_interactions: List[Dict[str, str]] = field(default_factory=list)
    
    # Summary
    summary: str = ""
    
    def to_prompt(self) -> str:
        """Convert context to prompt format."""
        sections = []
        
        if self.rules:
            sections.append("## Rules\n" + "\n".join(f"- {r['content']}" for r in self.rules))
        
        if self.preferences:
            sections.append("## User Preferences\n" + "\n".join(f"- {p['content']}" for p in self.preferences))
        
        if self.corrections:
            sections.append("## Past Corrections\n" + "\n".join(f"- {c['content']}" for c in self.corrections))
        
        if self.patterns:
            sections.append("## Code Patterns\n" + "\n".join(f"- {p['content']}" for p in self.patterns))
        
        return "\n\n".join(sections)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "rules": self.rules,
            "preferences": self.preferences,
            "patterns": self.patterns,
            "facts": self.facts,
            "corrections": self.corrections,
            "past_interactions": self.past_interactions,
            "summary": self.summary,
        }


class ContextBuilder:
    """
    Builds context for the agent from knowledge and memories.
    
    Combines:
    - Knowledge items (rules, preferences, patterns)
    - Memories (corrections, interactions)
    - File/project context
    - User history
    """
    
    def __init__(
        self,
        knowledge_store: KnowledgeStore,
        memory_store: MemoryStore,
    ):
        """Initialize context builder.
        
        Args:
            knowledge_store: Knowledge store
            memory_store: Memory store
        """
        self.knowledge = knowledge_store
        self.memories = memory_store
    
    def build(
        self,
        file_path: str,
        intent: str,
        user_id: Optional[str] = None,
        max_items: int = 20,
    ) -> BuiltContext:
        """Build context for a request.
        
        Args:
            file_path: Current file path
            intent: User intent
            user_id: Current user
            max_items: Maximum items per category
            
        Returns:
            Built context
        """
        context = BuiltContext()
        
        # Get knowledge items
        knowledge_items = self.knowledge.get_for_context(file_path, intent)
        
        for item in knowledge_items:
            item_dict = {"title": item.title, "content": item.content}
            
            if item.type == KnowledgeType.RULE:
                context.rules.append(item_dict)
            elif item.type == KnowledgeType.PREFERENCE:
                context.preferences.append(item_dict)
            elif item.type == KnowledgeType.PATTERN:
                context.patterns.append(item_dict)
            elif item.type == KnowledgeType.FACT:
                context.facts.append(item_dict)
            
            # Record usage
            self.knowledge.record_usage(item.id)
        
        # Get memories
        memories = self.memories.get_context_memories(file_path, intent, user_id)
        
        for memory in memories:
            mem_dict = {"content": memory.content, "summary": memory.summary}
            
            if memory.type == MemoryType.CORRECTION:
                context.corrections.append(mem_dict)
            elif memory.type == MemoryType.PREFERENCE:
                context.preferences.append({"title": "Preference", "content": memory.content})
            elif memory.type == MemoryType.INTERACTION:
                context.past_interactions.append(mem_dict)
        
        # Limit items
        context.rules = context.rules[:max_items]
        context.preferences = context.preferences[:max_items]
        context.patterns = context.patterns[:max_items]
        context.corrections = context.corrections[:max_items]
        
        # Generate summary
        context.summary = self._generate_summary(context)
        
        return context
    
    def _generate_summary(self, context: BuiltContext) -> str:
        """Generate a summary of the context."""
        parts = []
        
        if context.rules:
            parts.append(f"{len(context.rules)} rules apply")
        
        if context.preferences:
            parts.append(f"{len(context.preferences)} preferences noted")
        
        if context.corrections:
            parts.append(f"{len(context.corrections)} past corrections to consider")
        
        if context.patterns:
            parts.append(f"{len(context.patterns)} code patterns available")
        
        return ". ".join(parts) + "." if parts else "No specific context."
    
    def add_rule(
        self,
        title: str,
        rule: str,
        scope_path: Optional[str] = None,
    ) -> KnowledgeItem:
        """Add a coding rule.
        
        Args:
            title: Rule title
            rule: Rule content
            scope_path: Optional scope
            
        Returns:
            Created knowledge item
        """
        from .items import KnowledgeScope
        
        scope = KnowledgeScope.DIRECTORY if scope_path else KnowledgeScope.GLOBAL
        
        return self.knowledge.create(
            type=KnowledgeType.RULE,
            title=title,
            content=rule,
            scope=scope,
            scope_path=scope_path,
            priority=10,
        )
    
    def add_preference(
        self,
        preference: str,
        user_id: Optional[str] = None,
    ) -> Memory:
        """Add a user preference.
        
        Args:
            preference: Preference content
            user_id: User
            
        Returns:
            Created memory
        """
        return self.memories.remember_preference(preference, user_id)
    
    def record_correction(
        self,
        original: str,
        corrected: str,
        user_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Memory:
        """Record a correction.
        
        Args:
            original: What was done
            corrected: What was wanted
            user_id: User
            context: Additional context
            
        Returns:
            Created memory
        """
        return self.memories.remember_correction(original, corrected, user_id, context)
    
    def search(
        self,
        query: str,
        limit: int = 10,
    ) -> Dict[str, List[Any]]:
        """Search across knowledge and memories.
        
        Args:
            query: Search query
            limit: Maximum results per category
            
        Returns:
            Search results
        """
        knowledge_results = self.knowledge.search(query, limit=limit)
        memory_results = self.memories.recall(query, limit=limit)
        
        return {
            "knowledge": [
                {"id": k.id, "title": k.title, "content": k.content, "type": k.type.value}
                for k in knowledge_results
            ],
            "memories": [
                {"id": m.id, "content": m.content, "type": m.type.value}
                for m in memory_results
            ],
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get context builder statistics."""
        return {
            "knowledge": {
                "total": len(self.knowledge._items),
                "by_type": {
                    t.value: len([i for i in self.knowledge._items.values() if i.type == t])
                    for t in KnowledgeType
                },
            },
            "memories": self.memories.get_stats(),
        }

