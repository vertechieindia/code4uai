"""
Conversation Intelligence Engine

This is where Otter stops — we don't.

Converts raw transcripts/messages into:
- Classified segments (requirement, decision, risk, etc.)
- Extracted entities (systems, deadlines, constraints)
- Structured intent

Uses LLM for classification, NOT free text generation.
"""

from .classifier import ConversationClassifier
from .engine import ConversationIntelligence
from .entities import EntityExtractor

__all__ = [
    "ConversationClassifier",
    "ConversationIntelligence",
    "EntityExtractor",
]

