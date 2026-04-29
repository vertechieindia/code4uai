"""Conversation Intelligence Engine."""

from __future__ import annotations
import uuid
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from ..models import (
    Conversation,
    ConversationSegment,
    SegmentType,
)
from .classifier import ConversationClassifier
from .entities import EntityExtractor


@dataclass
class IntelligenceResult:
    """Result of conversation intelligence processing."""
    conversation_id: str
    segments: List[ConversationSegment]
    
    # Summary counts
    total_segments: int = 0
    requirements: int = 0
    constraints: int = 0
    decisions: int = 0
    open_questions: int = 0
    risks: int = 0
    action_items: int = 0
    
    # Processing metadata
    processed_at: datetime = field(default_factory=datetime.utcnow)
    processing_time_ms: float = 0.0


class ConversationIntelligence:
    """
    Conversation Intelligence Engine.
    
    This is where Otter stops — we don't.
    
    Converts raw transcripts + messages into:
    - Classified segments
    - Extracted entities
    - Structured intent
    """
    
    def __init__(
        self,
        llm_client=None,
        use_llm: bool = True,
    ):
        """Initialize intelligence engine.
        
        Args:
            llm_client: Optional LLM client
            use_llm: Whether to use LLM for classification
        """
        self.classifier = ConversationClassifier(llm_client)
        self.extractor = EntityExtractor(llm_client)
        self.use_llm = use_llm
    
    async def process(
        self,
        conversation: Conversation,
    ) -> IntelligenceResult:
        """Process a conversation.
        
        Args:
            conversation: Conversation to process
            
        Returns:
            Intelligence result with classified segments
        """
        start_time = datetime.utcnow()
        segments: List[ConversationSegment] = []
        
        # Process messages
        for msg in conversation.messages:
            segment = await self._process_message(
                conversation_id=conversation.id,
                speaker=msg.speaker.name,
                text=msg.text,
                timestamp=msg.timestamp.isoformat() if msg.timestamp else "",
            )
            segments.append(segment)
        
        # Process transcript segments
        for i, ts in enumerate(conversation.transcript_segments):
            segment = await self._process_message(
                conversation_id=conversation.id,
                speaker=ts.get("speaker", "Unknown"),
                text=ts.get("text", ""),
                timestamp=ts.get("timestamp", ""),
            )
            segments.append(segment)
        
        # If only raw transcript, split and process
        if conversation.transcript and not conversation.transcript_segments:
            transcript_segments = self._split_transcript(conversation.transcript)
            for ts in transcript_segments:
                segment = await self._process_message(
                    conversation_id=conversation.id,
                    speaker=ts["speaker"],
                    text=ts["text"],
                    timestamp=ts.get("timestamp", ""),
                )
                segments.append(segment)
        
        # Calculate counts
        result = IntelligenceResult(
            conversation_id=conversation.id,
            segments=segments,
            total_segments=len(segments),
        )
        
        for seg in segments:
            if seg.type == SegmentType.REQUIREMENT:
                result.requirements += 1
            elif seg.type == SegmentType.CONSTRAINT:
                result.constraints += 1
            elif seg.type == SegmentType.DECISION:
                result.decisions += 1
            elif seg.type == SegmentType.OPEN_QUESTION:
                result.open_questions += 1
            elif seg.type == SegmentType.RISK:
                result.risks += 1
            elif seg.type == SegmentType.ACTION_ITEM:
                result.action_items += 1
        
        result.processing_time_ms = (
            datetime.utcnow() - start_time
        ).total_seconds() * 1000
        
        return result
    
    async def _process_message(
        self,
        conversation_id: str,
        speaker: str,
        text: str,
        timestamp: str,
    ) -> ConversationSegment:
        """Process a single message/segment.
        
        Args:
            conversation_id: Parent conversation ID
            speaker: Speaker name
            text: Message text
            timestamp: Timestamp string
            
        Returns:
            Classified conversation segment
        """
        # Skip empty or very short segments
        if not text or len(text.strip()) < 5:
            return ConversationSegment(
                id=str(uuid.uuid4()),
                conversation_id=conversation_id,
                speaker=speaker,
                text=text,
                timestamp=timestamp,
                type=SegmentType.NON_TECHNICAL,
                confidence=1.0,
            )
        
        # Classify
        if self.use_llm:
            classification = await self.classifier.classify(speaker, text)
        else:
            classification = self.classifier.classify_rule_based(speaker, text)
        
        # Extract entities
        entities = self.extractor.extract(text)
        
        return ConversationSegment(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            speaker=speaker,
            text=text,
            timestamp=timestamp,
            type=classification.segment_type,
            confidence=classification.confidence,
            entities=entities.to_dict(),
        )
    
    def _split_transcript(self, transcript: str) -> List[Dict[str, str]]:
        """Split raw transcript into speaker segments.
        
        Args:
            transcript: Raw transcript text
            
        Returns:
            List of {speaker, text, timestamp} dicts
        """
        segments = []
        current_speaker = "Unknown"
        current_text = []
        
        for line in transcript.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Check for speaker pattern [Speaker]: or [Speaker]
            if line.startswith('[') and ']:' in line:
                # Save current segment
                if current_text:
                    segments.append({
                        "speaker": current_speaker,
                        "text": ' '.join(current_text),
                    })
                
                # Parse new speaker
                parts = line.split(']:', 1)
                current_speaker = parts[0][1:]  # Remove [
                current_text = [parts[1].strip()] if len(parts) > 1 else []
            else:
                current_text.append(line)
        
        # Don't forget last segment
        if current_text:
            segments.append({
                "speaker": current_speaker,
                "text": ' '.join(current_text),
            })
        
        return segments
    
    def filter_segments(
        self,
        segments: List[ConversationSegment],
        types: Optional[List[SegmentType]] = None,
        min_confidence: float = 0.0,
    ) -> List[ConversationSegment]:
        """Filter segments by type and confidence.
        
        Args:
            segments: Segments to filter
            types: Types to include (None = all)
            min_confidence: Minimum confidence threshold
            
        Returns:
            Filtered segments
        """
        result = []
        for seg in segments:
            if types and seg.type not in types:
                continue
            if seg.confidence < min_confidence:
                continue
            result.append(seg)
        return result
    
    def get_requirements_only(
        self,
        segments: List[ConversationSegment],
        min_confidence: float = 0.5,
    ) -> List[ConversationSegment]:
        """Get only requirement segments.
        
        Args:
            segments: All segments
            min_confidence: Minimum confidence
            
        Returns:
            Requirement segments only
        """
        return self.filter_segments(
            segments,
            types=[SegmentType.REQUIREMENT, SegmentType.CONSTRAINT],
            min_confidence=min_confidence,
        )
    
    def get_actionable_items(
        self,
        segments: List[ConversationSegment],
    ) -> Dict[str, List[ConversationSegment]]:
        """Get actionable items grouped by type.
        
        Args:
            segments: All segments
            
        Returns:
            Dict of type -> segments
        """
        actionable_types = [
            SegmentType.REQUIREMENT,
            SegmentType.CONSTRAINT,
            SegmentType.DECISION,
            SegmentType.ACTION_ITEM,
            SegmentType.RISK,
        ]
        
        result: Dict[str, List[ConversationSegment]] = {t.value: [] for t in actionable_types}
        
        for seg in segments:
            if seg.type in actionable_types:
                result[seg.type.value].append(seg)
        
        return result

