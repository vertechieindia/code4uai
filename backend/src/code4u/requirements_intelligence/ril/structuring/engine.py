"""Requirement Structuring Engine."""

from __future__ import annotations
import json
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field

from ..models import (
    ConversationSegment,
    StructuredRequirement,
    RequirementType,
    RequirementPriority,
    RequirementStatus,
    SegmentType,
    ConversationPlatform,
)
from .templates import (
    RequirementTemplate,
    STRUCTURING_PROMPT,
    BATCH_STRUCTURING_PROMPT,
)


@dataclass
class StructuringResult:
    """Result of requirement structuring."""
    requirements: List[StructuredRequirement]
    processed_segments: int
    structuring_time_ms: float
    
    # Stats
    functional_count: int = 0
    technical_count: int = 0
    security_count: int = 0
    compliance_count: int = 0


class RequirementStructurer:
    """
    Requirement Structuring Engine.
    
    Converts human language → engineering-grade requirements.
    
    This is not a summary.
    This is a machine-usable contract.
    """
    
    def __init__(
        self,
        tenant_id: str = "default",
        llm_client=None,
    ):
        """Initialize structurer.
        
        Args:
            tenant_id: Tenant identifier
            llm_client: Optional LLM client
        """
        self.tenant_id = tenant_id
        self.llm_client = llm_client
        self.template = RequirementTemplate()
        self._counter = 0
    
    async def structure(
        self,
        segment: ConversationSegment,
        context: Optional[str] = None,
        source_platform: Optional[ConversationPlatform] = None,
        source_url: Optional[str] = None,
    ) -> Optional[StructuredRequirement]:
        """Structure a single segment into a requirement.
        
        Args:
            segment: Classified segment
            context: Optional surrounding context
            source_platform: Source platform
            source_url: URL back to source
            
        Returns:
            Structured requirement or None if not applicable
        """
        # Skip non-requirement segments
        if segment.type not in [
            SegmentType.REQUIREMENT,
            SegmentType.CONSTRAINT,
            SegmentType.DECISION,
        ]:
            return None
        
        # Use LLM if available
        if self.llm_client:
            requirement = await self._structure_with_llm(
                segment, context, source_platform, source_url
            )
        else:
            requirement = self._structure_rule_based(
                segment, source_platform, source_url
            )
        
        return requirement
    
    async def structure_batch(
        self,
        segments: List[ConversationSegment],
        conversation_id: str,
        source_platform: Optional[ConversationPlatform] = None,
        source_url: Optional[str] = None,
    ) -> StructuringResult:
        """Structure multiple segments into requirements.
        
        Args:
            segments: List of segments
            conversation_id: Source conversation ID
            source_platform: Source platform
            source_url: URL back to source
            
        Returns:
            Structuring result with all requirements
        """
        start_time = datetime.utcnow()
        
        # Filter to actionable segments
        actionable = [
            s for s in segments
            if s.type in [
                SegmentType.REQUIREMENT,
                SegmentType.CONSTRAINT,
                SegmentType.DECISION,
            ]
        ]
        
        requirements: List[StructuredRequirement] = []
        
        if self.llm_client and len(actionable) > 1:
            # Batch process with LLM
            requirements = await self._batch_structure_llm(
                actionable, conversation_id, source_platform, source_url
            )
        else:
            # Process individually
            for seg in actionable:
                req = await self.structure(
                    seg, None, source_platform, source_url
                )
                if req:
                    req.source_conversation_id = conversation_id
                    requirements.append(req)
        
        # Calculate stats
        result = StructuringResult(
            requirements=requirements,
            processed_segments=len(actionable),
            structuring_time_ms=(
                datetime.utcnow() - start_time
            ).total_seconds() * 1000,
        )
        
        for req in requirements:
            if req.type == RequirementType.FUNCTIONAL:
                result.functional_count += 1
            elif req.type == RequirementType.TECHNICAL:
                result.technical_count += 1
            elif req.type == RequirementType.SECURITY:
                result.security_count += 1
            elif req.type == RequirementType.COMPLIANCE:
                result.compliance_count += 1
        
        return result
    
    async def _structure_with_llm(
        self,
        segment: ConversationSegment,
        context: Optional[str],
        source_platform: Optional[ConversationPlatform],
        source_url: Optional[str],
    ) -> StructuredRequirement:
        """Structure using LLM."""
        entities = segment.entities or {}
        
        prompt = STRUCTURING_PROMPT.format(
            speaker=segment.speaker,
            role=self._infer_role(segment.speaker),
            text=segment.text,
            context=context or "None",
            systems=", ".join(entities.get("systems", [])) or "None detected",
            technologies=", ".join(entities.get("technologies", [])) or "None detected",
            constraints=", ".join(entities.get("constraints", [])) or "None detected",
            deadlines=str(entities.get("deadlines", [])) or "None detected",
        )
        
        try:
            response = await self._call_llm(prompt)
            data = json.loads(response)
            
            return self._create_requirement(
                data=data,
                segment=segment,
                source_platform=source_platform,
                source_url=source_url,
            )
        except Exception:
            # Fall back to rule-based
            return self._structure_rule_based(
                segment, source_platform, source_url
            )
    
    async def _batch_structure_llm(
        self,
        segments: List[ConversationSegment],
        conversation_id: str,
        source_platform: Optional[ConversationPlatform],
        source_url: Optional[str],
    ) -> List[StructuredRequirement]:
        """Batch structure using LLM."""
        # Format segments for prompt
        segment_texts = []
        segment_map = {}
        
        for seg in segments:
            segment_texts.append(
                f"[ID: {seg.id}] [{seg.speaker}]: {seg.text}"
            )
            segment_map[seg.id] = seg
        
        prompt = BATCH_STRUCTURING_PROMPT.format(
            segments="\n".join(segment_texts)
        )
        
        try:
            response = await self._call_llm(prompt)
            data = json.loads(response)
            
            requirements = []
            for item in data:
                source_ids = item.get("source_segment_ids", [])
                
                req = self._create_requirement(
                    data=item,
                    segment=None,
                    source_platform=source_platform,
                    source_url=source_url,
                )
                req.source_conversation_id = conversation_id
                req.source_segment_ids = source_ids
                
                # Get original text from segments
                original_texts = []
                for sid in source_ids:
                    if sid in segment_map:
                        original_texts.append(segment_map[sid].text)
                req.original_text = " | ".join(original_texts)
                
                requirements.append(req)
            
            return requirements
        except Exception:
            # Fall back to individual processing
            requirements = []
            for seg in segments:
                req = self._structure_rule_based(
                    seg, source_platform, source_url
                )
                req.source_conversation_id = conversation_id
                requirements.append(req)
            return requirements
    
    def _structure_rule_based(
        self,
        segment: ConversationSegment,
        source_platform: Optional[ConversationPlatform],
        source_url: Optional[str],
    ) -> StructuredRequirement:
        """Structure using rule-based approach."""
        text_lower = segment.text.lower()
        entities = segment.entities or {}
        
        # Determine type
        req_type = self._infer_type(text_lower)
        
        # Determine priority
        priority = self._infer_priority(text_lower)
        
        # Extract systems
        systems = self._extract_systems(text_lower)
        systems.extend(entities.get("systems", []))
        systems = list(set(systems))
        
        # Extract constraints
        constraints = entities.get("constraints", [])
        
        # Generate title
        title = self._generate_title(segment.text, req_type)
        
        return StructuredRequirement(
            id=self._generate_id(),
            tenant_id=self.tenant_id,
            title=title,
            description=segment.text,
            type=req_type,
            priority=priority,
            status=RequirementStatus.DRAFT,
            systems=systems,
            constraints=constraints,
            source_platform=source_platform,
            source_segment_ids=[segment.id],
            source_url=source_url,
            original_text=segment.text,
            requested_by=segment.speaker,
        )
    
    def _create_requirement(
        self,
        data: Dict[str, Any],
        segment: Optional[ConversationSegment],
        source_platform: Optional[ConversationPlatform],
        source_url: Optional[str],
    ) -> StructuredRequirement:
        """Create requirement from structured data."""
        # Parse type
        try:
            req_type = RequirementType(data.get("type", "functional"))
        except ValueError:
            req_type = RequirementType.FUNCTIONAL
        
        # Parse priority
        try:
            priority = RequirementPriority(data.get("priority", "medium"))
        except ValueError:
            priority = RequirementPriority.MEDIUM
        
        return StructuredRequirement(
            id=self._generate_id(),
            tenant_id=self.tenant_id,
            title=data.get("title", "Untitled Requirement")[:100],
            description=data.get("description", ""),
            type=req_type,
            priority=priority,
            status=RequirementStatus.DRAFT,
            systems=data.get("systems", []),
            services=data.get("services", []),
            constraints=data.get("constraints", []),
            dependencies=data.get("dependencies", []),
            acceptance_criteria=data.get("acceptance_criteria", []),
            source_platform=source_platform,
            source_segment_ids=[segment.id] if segment else [],
            source_url=source_url,
            original_text=segment.text if segment else "",
            requested_by=segment.speaker if segment else None,
        )
    
    def _infer_type(self, text: str) -> RequirementType:
        """Infer requirement type from text."""
        for req_type, keywords in self.template.TYPE_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return req_type
        return RequirementType.FUNCTIONAL
    
    def _infer_priority(self, text: str) -> RequirementPriority:
        """Infer priority from text."""
        for priority, keywords in self.template.PRIORITY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return priority
        return RequirementPriority.MEDIUM
    
    def _extract_systems(self, text: str) -> List[str]:
        """Extract affected systems from text."""
        systems = []
        for system, keywords in self.template.SYSTEM_MAPPINGS.items():
            if any(kw in text for kw in keywords):
                systems.append(system)
        return systems
    
    def _generate_title(self, text: str, req_type: RequirementType) -> str:
        """Generate a concise title from text."""
        # Take first sentence or first 100 chars
        first_sentence = text.split('.')[0].strip()
        if len(first_sentence) > 100:
            first_sentence = first_sentence[:97] + "..."
        
        # Capitalize and prefix with type indicator
        prefix_map = {
            RequirementType.FUNCTIONAL: "Implement",
            RequirementType.TECHNICAL: "Technical:",
            RequirementType.SECURITY: "Security:",
            RequirementType.COMPLIANCE: "Compliance:",
            RequirementType.PERFORMANCE: "Performance:",
            RequirementType.INTEGRATION: "Integrate",
        }
        
        prefix = prefix_map.get(req_type, "")
        if prefix and not first_sentence.lower().startswith(prefix.lower()):
            return f"{prefix} {first_sentence}"
        
        return first_sentence
    
    def _infer_role(self, speaker: str) -> str:
        """Infer role from speaker name."""
        speaker_lower = speaker.lower()
        
        role_patterns = {
            "pm": ["pm", "product", "manager"],
            "engineer": ["eng", "dev", "developer", "backend", "frontend"],
            "designer": ["design", "ux", "ui"],
            "qa": ["qa", "test", "quality"],
            "lead": ["lead", "principal", "staff", "senior"],
            "executive": ["cto", "vp", "director", "ceo"],
        }
        
        for role, patterns in role_patterns.items():
            if any(p in speaker_lower for p in patterns):
                return role
        
        return "unknown"
    
    def _generate_id(self) -> str:
        """Generate a requirement ID."""
        self._counter += 1
        return f"REQ-{self._counter:04d}"
    
    async def _call_llm(self, prompt: str) -> str:
        """Call LLM."""
        if hasattr(self.llm_client, 'complete'):
            return await self.llm_client.complete(
                prompt=prompt,
                temperature=0.0,
                max_tokens=1000,
            )
        
        # Default to OpenAI-compatible API
        import os
        import httpx
        
        api_key = os.getenv("OPENAI_API_KEY", "")
        base_url = os.getenv("LLM_API_URL", "https://api.openai.com/v1")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                    "max_tokens": 1000,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

