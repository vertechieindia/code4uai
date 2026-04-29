"""Conversation segment classifier."""

from __future__ import annotations
import json
import uuid
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from ..models import SegmentType, ConversationSegment


@dataclass
class ClassificationResult:
    """Result of segment classification."""
    segment_type: SegmentType
    confidence: float
    entities: Dict[str, Any]
    reasoning: str


CLASSIFICATION_PROMPT = """You are a conversation classifier for engineering teams.

Classify the following conversation segment into EXACTLY ONE category:
- requirement: A feature request, user story, or functional need
- constraint: A limitation, restriction, or non-functional requirement
- decision: A choice that was made or agreed upon
- open_question: An unresolved question or uncertainty
- risk: A potential problem, concern, or blocker
- action_item: A specific task assigned to someone
- context: Background information or explanation
- non_technical: Off-topic or social conversation

Also extract any relevant entities:
- systems: Software systems, services, or components mentioned
- people: Names of people or roles mentioned
- dates: Deadlines, milestones, or time references
- technologies: Technologies, frameworks, or tools mentioned
- constraints: Specific constraints (compliance, performance, security)

SEGMENT:
Speaker: {speaker}
Text: {text}

Respond in JSON format ONLY:
{{
  "type": "requirement|constraint|decision|open_question|risk|action_item|context|non_technical",
  "confidence": 0.0-1.0,
  "entities": {{
    "systems": [],
    "people": [],
    "dates": [],
    "technologies": [],
    "constraints": []
  }},
  "reasoning": "Brief explanation"
}}"""


class ConversationClassifier:
    """
    Classifies conversation segments using LLM.
    
    Classification-only, no free text generation.
    Deterministic and auditable.
    """
    
    def __init__(
        self,
        llm_client=None,
        model: str = "gpt-4o-mini",
    ):
        """Initialize classifier.
        
        Args:
            llm_client: Optional LLM client
            model: Model to use for classification
        """
        self.llm_client = llm_client
        self.model = model
    
    async def classify(
        self,
        speaker: str,
        text: str,
        context: Optional[str] = None,
    ) -> ClassificationResult:
        """Classify a conversation segment.
        
        Args:
            speaker: Speaker name/role
            text: Segment text
            context: Optional surrounding context
            
        Returns:
            Classification result
        """
        prompt = CLASSIFICATION_PROMPT.format(
            speaker=speaker,
            text=text,
        )
        
        if context:
            prompt += f"\n\nCONTEXT:\n{context}"
        
        # Call LLM
        response = await self._call_llm(prompt)
        
        # Parse response
        try:
            data = json.loads(response)
            
            segment_type = SegmentType(data.get("type", "context"))
            confidence = float(data.get("confidence", 0.5))
            entities = data.get("entities", {})
            reasoning = data.get("reasoning", "")
            
            return ClassificationResult(
                segment_type=segment_type,
                confidence=confidence,
                entities=entities,
                reasoning=reasoning,
            )
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback
            return ClassificationResult(
                segment_type=SegmentType.CONTEXT,
                confidence=0.0,
                entities={},
                reasoning=f"Failed to parse: {e}",
            )
    
    async def classify_batch(
        self,
        segments: List[Dict[str, str]],
    ) -> List[ClassificationResult]:
        """Classify multiple segments.
        
        Args:
            segments: List of {speaker, text} dicts
            
        Returns:
            List of classification results
        """
        results = []
        for seg in segments:
            result = await self.classify(
                speaker=seg.get("speaker", "Unknown"),
                text=seg.get("text", ""),
            )
            results.append(result)
        return results
    
    async def _call_llm(self, prompt: str) -> str:
        """Call LLM for classification.
        
        Args:
            prompt: Prompt to send
            
        Returns:
            LLM response text
        """
        if self.llm_client:
            # Use provided client
            response = await self.llm_client.complete(
                prompt=prompt,
                model=self.model,
                temperature=0.0,  # Deterministic
                max_tokens=500,
            )
            return response
        
        # Default: use httpx with OpenAI-compatible API
        import os
        import httpx
        
        api_key = os.getenv("OPENAI_API_KEY", "")
        base_url = os.getenv("LLM_API_URL", "https://api.openai.com/v1")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                    "max_tokens": 500,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    
    def classify_rule_based(
        self,
        speaker: str,
        text: str,
    ) -> ClassificationResult:
        """Rule-based classification (fallback, no LLM).
        
        Args:
            speaker: Speaker name
            text: Segment text
            
        Returns:
            Classification result
        """
        text_lower = text.lower()
        
        # Requirements keywords
        requirement_keywords = [
            "we need", "must have", "should have", "required",
            "feature", "functionality", "user story", "as a",
            "want to", "ability to", "support for",
        ]
        
        # Constraint keywords
        constraint_keywords = [
            "must be", "cannot", "should not", "limitation",
            "compliance", "soc2", "iso", "gdpr", "hipaa",
            "performance", "latency", "security", "before",
        ]
        
        # Decision keywords
        decision_keywords = [
            "we decided", "agreed", "will use", "going with",
            "chosen", "selected", "final decision", "approved",
        ]
        
        # Question keywords
        question_keywords = [
            "?", "do we", "should we", "can we", "what if",
            "how do", "unclear", "not sure", "question",
        ]
        
        # Risk keywords
        risk_keywords = [
            "risk", "concern", "worried", "might fail",
            "blocker", "problem", "issue", "challenge",
        ]
        
        # Action keywords
        action_keywords = [
            "will do", "action item", "todo", "task",
            "assigned to", "responsible for", "follow up",
        ]
        
        # Check patterns
        entities: Dict[str, Any] = {"systems": [], "people": [], "dates": [], "technologies": [], "constraints": []}
        
        if any(kw in text_lower for kw in requirement_keywords):
            return ClassificationResult(
                segment_type=SegmentType.REQUIREMENT,
                confidence=0.7,
                entities=entities,
                reasoning="Rule-based: requirement keywords detected",
            )
        
        if any(kw in text_lower for kw in constraint_keywords):
            return ClassificationResult(
                segment_type=SegmentType.CONSTRAINT,
                confidence=0.7,
                entities=entities,
                reasoning="Rule-based: constraint keywords detected",
            )
        
        if any(kw in text_lower for kw in decision_keywords):
            return ClassificationResult(
                segment_type=SegmentType.DECISION,
                confidence=0.7,
                entities=entities,
                reasoning="Rule-based: decision keywords detected",
            )
        
        if any(kw in text_lower for kw in question_keywords):
            return ClassificationResult(
                segment_type=SegmentType.OPEN_QUESTION,
                confidence=0.7,
                entities=entities,
                reasoning="Rule-based: question keywords detected",
            )
        
        if any(kw in text_lower for kw in risk_keywords):
            return ClassificationResult(
                segment_type=SegmentType.RISK,
                confidence=0.7,
                entities=entities,
                reasoning="Rule-based: risk keywords detected",
            )
        
        if any(kw in text_lower for kw in action_keywords):
            return ClassificationResult(
                segment_type=SegmentType.ACTION_ITEM,
                confidence=0.7,
                entities=entities,
                reasoning="Rule-based: action keywords detected",
            )
        
        # Default to context
        return ClassificationResult(
            segment_type=SegmentType.CONTEXT,
            confidence=0.5,
            entities=entities,
            reasoning="Rule-based: no specific pattern matched",
        )

