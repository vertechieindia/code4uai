"""
Requirements Intelligence Layer - Full Orchestrator

The complete pipeline:

Slack / Teams / Zoom
        ↓
Conversation Ingestion Layer
        ↓
Speech-to-Text + Message Capture
        ↓
Conversation Intelligence Engine
        ↓
Requirement Structuring Engine
        ↓
Knowledge Graph (Requirements Nodes)
        ↓
Agent Planner (Optional Execution)

Otter stops at transcription + summary.
code4u.ai goes all the way to engineering execution.

That's the moat.
"""

from __future__ import annotations
import uuid
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

from .models import (
    Conversation,
    ConversationSegment,
    StructuredRequirement,
    ConversationPlatform,
)
from .ingestion import SlackIngestion, TeamsIngestion, ZoomIngestion
from .stt import TranscriptionService
from .intelligence import ConversationIntelligence
from .structuring import RequirementStructurer
from .graph import RequirementGraphIntegration
from .agent import RequirementPlanner, RequirementExecutor, CommandHandler
from .security import ConsentManager, PIIRedactor, RILAuditLogger


@dataclass
class PipelineResult:
    """Result of running the full RIL pipeline."""
    conversation_id: str
    
    # Processing stats
    messages_captured: int = 0
    segments_classified: int = 0
    requirements_extracted: int = 0
    pii_redactions: int = 0
    
    # Outputs
    requirements: List[StructuredRequirement] = field(default_factory=list)
    decisions: List[Dict[str, Any]] = field(default_factory=list)
    action_items: List[Dict[str, Any]] = field(default_factory=list)
    open_questions: List[Dict[str, Any]] = field(default_factory=list)
    
    # Timing
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    processing_time_ms: float = 0.0
    
    # Status
    status: str = "pending"
    error: Optional[str] = None


class RILOrchestrator:
    """
    Requirements Intelligence Layer Orchestrator.
    
    Coordinates the full pipeline from conversation to execution.
    
    The system where decisions turn into shipped code.
    """
    
    def __init__(
        self,
        tenant_id: str = "default",
        llm_client=None,
        embedding_service=None,
        agent_coordinator=None,
    ):
        """Initialize orchestrator.
        
        Args:
            tenant_id: Tenant identifier
            llm_client: LLM client for AI processing
            embedding_service: Service for generating embeddings
            agent_coordinator: Coordinator for agent execution
        """
        self.tenant_id = tenant_id
        
        # Ingestion services
        self.ingestion = {
            "slack": SlackIngestion(tenant_id),
            "teams": TeamsIngestion(tenant_id),
            "zoom": ZoomIngestion(tenant_id),
        }
        
        # Processing services
        self.transcription = TranscriptionService()
        self.intelligence = ConversationIntelligence(llm_client)
        self.structurer = RequirementStructurer(tenant_id, llm_client)
        
        # Graph integration
        self.graph = RequirementGraphIntegration(
            embedding_service=embedding_service
        )
        
        # Agent services
        self.planner = RequirementPlanner(llm_client=llm_client)
        self.executor = RequirementExecutor(
            planner=self.planner,
            agent_coordinator=agent_coordinator,
        )
        
        # Security services
        self.consent = ConsentManager()
        self.redactor = PIIRedactor()
        self.audit = RILAuditLogger()
        
        # Command handler
        self.commands = CommandHandler(
            executor=self.executor,
            planner=self.planner,
            graph_integration=self.graph,
        )
        
        # Active pipelines
        self._pipelines: Dict[str, PipelineResult] = {}
    
    async def run_pipeline(
        self,
        conversation: Conversation,
        redact_pii: bool = True,
        use_llm: bool = True,
        auto_add_to_graph: bool = True,
    ) -> PipelineResult:
        """
        Run the full RIL pipeline on a conversation.
        
        Steps:
        1. PII Redaction (optional)
        2. Segment Classification
        3. Entity Extraction
        4. Requirement Structuring
        5. Graph Integration
        
        Args:
            conversation: Captured conversation
            redact_pii: Whether to redact PII
            use_llm: Whether to use LLM for classification
            auto_add_to_graph: Whether to add to Knowledge Graph
            
        Returns:
            Pipeline result
        """
        result = PipelineResult(
            conversation_id=conversation.id,
            messages_captured=len(conversation.messages),
        )
        
        self._pipelines[conversation.id] = result
        
        try:
            # Step 1: PII Redaction
            if redact_pii:
                await self._redact_pii(conversation, result)
            
            # Step 2-3: Intelligence Processing (Classification + Entity Extraction)
            intel_result = await self._process_intelligence(
                conversation, result, use_llm
            )
            
            # Step 4: Requirement Structuring
            await self._structure_requirements(
                intel_result.segments,
                conversation,
                result,
            )
            
            # Step 5: Graph Integration
            if auto_add_to_graph:
                await self._add_to_graph(conversation, result)
            
            result.status = "completed"
            result.completed_at = datetime.utcnow()
            result.processing_time_ms = (
                result.completed_at - result.started_at
            ).total_seconds() * 1000
            
            # Audit log
            self.audit.log_requirements_extracted(
                tenant_id=self.tenant_id,
                conversation_id=conversation.id,
                requirements_count=len(result.requirements),
                requirement_ids=[r.id for r in result.requirements],
            )
            
        except Exception as e:
            result.status = "failed"
            result.error = str(e)
            result.completed_at = datetime.utcnow()
        
        return result
    
    async def _redact_pii(
        self,
        conversation: Conversation,
        result: PipelineResult,
    ) -> None:
        """Redact PII from conversation."""
        total_redactions = 0
        
        # Redact messages
        for msg in conversation.messages:
            redaction_result = self.redactor.redact(msg.text)
            msg.text = redaction_result.text
            total_redactions += len(redaction_result.redactions)
        
        # Redact transcript
        if conversation.transcript:
            redaction_result = self.redactor.redact(conversation.transcript)
            conversation.transcript = redaction_result.text
            total_redactions += len(redaction_result.redactions)
        
        result.pii_redactions = total_redactions
        
        if total_redactions > 0:
            self.audit.log_pii_redaction(
                tenant_id=self.tenant_id,
                conversation_id=conversation.id,
                redaction_stats={"total": total_redactions},
            )
    
    async def _process_intelligence(
        self,
        conversation: Conversation,
        result: PipelineResult,
        use_llm: bool,
    ):
        """Process conversation with intelligence engine."""
        self.intelligence.use_llm = use_llm
        intel_result = await self.intelligence.process(conversation)
        
        result.segments_classified = intel_result.total_segments
        
        # Extract non-requirement items
        actionable = self.intelligence.get_actionable_items(intel_result.segments)
        
        result.decisions = [
            {"id": s.id, "speaker": s.speaker, "text": s.text}
            for s in actionable.get("decision", [])
        ]
        
        result.action_items = [
            {"id": s.id, "speaker": s.speaker, "text": s.text}
            for s in actionable.get("action_item", [])
        ]
        
        result.open_questions = [
            {"id": s.id, "speaker": s.speaker, "text": s.text}
            for s in actionable.get("open_question", [])
        ]
        
        return intel_result
    
    async def _structure_requirements(
        self,
        segments: List[ConversationSegment],
        conversation: Conversation,
        result: PipelineResult,
    ) -> None:
        """Structure segments into requirements."""
        structuring_result = await self.structurer.structure_batch(
            segments=segments,
            conversation_id=conversation.id,
            source_platform=conversation.platform,
        )
        
        result.requirements = structuring_result.requirements
        result.requirements_extracted = len(structuring_result.requirements)
        
        # Add to executor for later execution
        for req in structuring_result.requirements:
            self.executor.add_requirement(req)
    
    async def _add_to_graph(
        self,
        conversation: Conversation,
        result: PipelineResult,
    ) -> None:
        """Add results to Knowledge Graph."""
        # Add requirements
        for req in result.requirements:
            await self.graph.add_requirement(req)
        
        # Add meeting
        await self.graph.add_meeting(
            conversation,
            requirements_count=len(result.requirements),
            decisions_count=len(result.decisions),
        )
        
        # Add decisions
        from .models import SegmentType
        for decision in result.decisions:
            # Find the segment
            for req in result.requirements:
                if req.source_segment_ids and decision["id"] in req.source_segment_ids:
                    segment = ConversationSegment(
                        id=decision["id"],
                        conversation_id=conversation.id,
                        speaker=decision["speaker"],
                        text=decision["text"],
                        timestamp="",
                        type=SegmentType.DECISION,
                    )
                    await self.graph.add_decision(
                        segment=segment,
                        title=decision["text"][:100],
                        chosen_option="",
                    )
                    break
    
    async def capture_and_process(
        self,
        platform: str,
        channel_id: Optional[str] = None,
        meeting_id: Optional[str] = None,
        wait_for_completion: bool = True,
    ) -> PipelineResult:
        """
        Capture a conversation and run the full pipeline.
        
        Args:
            platform: slack, teams, or zoom
            channel_id: Channel to capture
            meeting_id: Meeting to capture
            wait_for_completion: Whether to wait for capture to complete
            
        Returns:
            Pipeline result
        """
        ingestion = self.ingestion.get(platform)
        if not ingestion:
            raise ValueError(f"Unknown platform: {platform}")
        
        # Connect and start capture
        await ingestion.connect()
        conv_id = await ingestion.start_capture(
            channel_id=channel_id,
            meeting_id=meeting_id,
        )
        
        self.audit.log_capture_started(
            tenant_id=self.tenant_id,
            user_id="system",
            conversation_id=conv_id,
            platform=platform,
        )
        
        if not wait_for_completion:
            # Return immediately with pending status
            return PipelineResult(
                conversation_id=conv_id,
                status="capturing",
            )
        
        # Stop capture and get conversation
        conversation = await ingestion.stop_capture(conv_id)
        
        # Run pipeline
        return await self.run_pipeline(conversation)
    
    async def process_from_transcript(
        self,
        transcript: str,
        platform: ConversationPlatform = ConversationPlatform.ZOOM,
        meeting_title: Optional[str] = None,
    ) -> PipelineResult:
        """
        Process a raw transcript directly.
        
        Args:
            transcript: Raw transcript text
            platform: Source platform
            meeting_title: Optional meeting title
            
        Returns:
            Pipeline result
        """
        # Create a conversation object
        conversation = Conversation(
            id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            platform=platform,
            platform_id="direct-transcript",
            type="meeting",
            title=meeting_title or "Uploaded Transcript",
            transcript=transcript,
        )
        
        return await self.run_pipeline(conversation)
    
    async def handle_command(
        self,
        command: str,
        user_id: str,
        channel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Handle a Slack/Teams command.
        
        Examples:
        - /code4u convert meeting-123 to plan
        - /code4u status exec-456
        - /code4u approve exec-789
        
        Args:
            command: Command text
            user_id: User ID
            channel_id: Channel ID
            
        Returns:
            Command result
        """
        return await self.commands.handle(
            command_text=command,
            user_id=user_id,
            tenant_id=self.tenant_id,
            channel_id=channel_id,
        )
    
    def get_pipeline_status(self, conversation_id: str) -> Optional[PipelineResult]:
        """Get pipeline status."""
        return self._pipelines.get(conversation_id)
    
    async def search_requirements(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search requirements."""
        nodes = await self.graph.search_requirements(
            query=query,
            tenant_id=self.tenant_id,
            limit=limit,
        )
        return [n.to_dict() for n in nodes]
    
    def get_traceability(
        self,
        requirement_id: str,
    ) -> Dict[str, Any]:
        """Get full traceability for a requirement."""
        return self.graph.get_traceability_chain(requirement_id)


def create_orchestrator(
    tenant_id: str = "default",
    llm_client=None,
) -> RILOrchestrator:
    """
    Factory function to create a configured RIL orchestrator.
    
    Args:
        tenant_id: Tenant identifier
        llm_client: Optional LLM client
        
    Returns:
        Configured orchestrator
    """
    return RILOrchestrator(
        tenant_id=tenant_id,
        llm_client=llm_client,
    )

