"""Knowledge Graph integration for requirements."""

from __future__ import annotations
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass

from ..models import (
    Conversation,
    StructuredRequirement,
    ConversationSegment,
    SegmentType,
)
from .nodes import (
    RequirementNode,
    DecisionNode,
    StakeholderNode,
    MeetingNode,
    RequirementNodeType,
    RequirementRelationType,
)


@dataclass
class GraphRelationship:
    """A relationship in the graph."""
    source_id: str
    target_id: str
    relationship_type: RequirementRelationType
    properties: Dict[str, Any] = None


class RequirementGraphIntegration:
    """
    Integrates requirements with the Knowledge Graph.
    
    Extends the existing Code Knowledge Graph with:
    - Requirement nodes
    - Decision nodes
    - Stakeholder nodes
    - Meeting nodes
    
    Requirements become:
    - Searchable
    - Traceable
    - Validatable
    - Agent-triggerable
    """
    
    def __init__(
        self,
        knowledge_graph=None,
        embedding_service=None,
    ):
        """Initialize integration.
        
        Args:
            knowledge_graph: Existing KnowledgeGraph instance
            embedding_service: Service for generating embeddings
        """
        self.knowledge_graph = knowledge_graph
        self.embedding_service = embedding_service
        
        # Local stores if no graph provided
        self._requirement_nodes: Dict[str, RequirementNode] = {}
        self._decision_nodes: Dict[str, DecisionNode] = {}
        self._stakeholder_nodes: Dict[str, StakeholderNode] = {}
        self._meeting_nodes: Dict[str, MeetingNode] = {}
        self._relationships: List[GraphRelationship] = []
    
    async def add_requirement(
        self,
        requirement: StructuredRequirement,
    ) -> RequirementNode:
        """Add a requirement to the graph.
        
        Args:
            requirement: Structured requirement
            
        Returns:
            Created requirement node
        """
        # Create node
        node = RequirementNode(
            id=requirement.id,
            title=requirement.title,
            description=requirement.description,
            requirement_type=requirement.type.value,
            priority=requirement.priority.value,
            status=requirement.status.value,
            tenant_id=requirement.tenant_id,
            source_conversation_id=requirement.source_conversation_id,
            source_platform=requirement.source_platform.value if requirement.source_platform else None,
            source_url=requirement.source_url,
            systems=requirement.systems,
            services=requirement.services,
            constraints=requirement.constraints,
            acceptance_criteria=requirement.acceptance_criteria,
        )
        
        # Generate embedding
        if self.embedding_service:
            text = f"{requirement.title}. {requirement.description}"
            node.embedding = await self.embedding_service.embed(text)
        
        # Store node
        self._requirement_nodes[node.id] = node
        
        # Add to main knowledge graph if available
        if self.knowledge_graph:
            self.knowledge_graph.add_node(
                node_id=node.id,
                node_type=RequirementNodeType.REQUIREMENT.value,
                properties=node.to_dict(),
            )
        
        # Create relationships
        await self._create_requirement_relationships(node, requirement)
        
        return node
    
    async def _create_requirement_relationships(
        self,
        node: RequirementNode,
        requirement: StructuredRequirement,
    ) -> None:
        """Create relationships for a requirement."""
        # Link to affected systems/services
        for system in requirement.systems:
            rel = GraphRelationship(
                source_id=node.id,
                target_id=system,
                relationship_type=RequirementRelationType.AFFECTS,
            )
            self._relationships.append(rel)
            
            if self.knowledge_graph:
                self.knowledge_graph.add_relationship(
                    source_id=node.id,
                    target_id=system,
                    relationship_type=RequirementRelationType.AFFECTS.value,
                )
        
        # Link to source meeting
        if requirement.source_conversation_id:
            rel = GraphRelationship(
                source_id=node.id,
                target_id=requirement.source_conversation_id,
                relationship_type=RequirementRelationType.DERIVED_FROM,
            )
            self._relationships.append(rel)
        
        # Link to requester
        if requirement.requested_by:
            stakeholder = await self.get_or_create_stakeholder(
                name=requirement.requested_by,
                tenant_id=requirement.tenant_id,
            )
            rel = GraphRelationship(
                source_id=stakeholder.id,
                target_id=node.id,
                relationship_type=RequirementRelationType.REQUESTED,
            )
            self._relationships.append(rel)
    
    async def add_meeting(
        self,
        conversation: Conversation,
        requirements_count: int = 0,
        decisions_count: int = 0,
    ) -> MeetingNode:
        """Add a meeting to the graph.
        
        Args:
            conversation: Conversation object
            requirements_count: Number of requirements extracted
            decisions_count: Number of decisions extracted
            
        Returns:
            Created meeting node
        """
        # Calculate duration
        duration = 0
        if conversation.started_at and conversation.ended_at:
            duration = int((conversation.ended_at - conversation.started_at).total_seconds() / 60)
        
        node = MeetingNode(
            id=conversation.id,
            title=conversation.title or f"Meeting {conversation.platform_id}",
            platform=conversation.platform.value,
            platform_id=conversation.platform_id,
            started_at=conversation.started_at,
            ended_at=conversation.ended_at,
            duration_minutes=duration,
            participant_count=len(conversation.speakers),
            participant_ids=[s.id for s in conversation.speakers],
            conversation_id=conversation.id,
            has_transcript=bool(conversation.transcript),
            requirements_count=requirements_count,
            decisions_count=decisions_count,
            tenant_id=conversation.tenant_id,
        )
        
        # Generate embedding from title
        if self.embedding_service and conversation.title:
            node.embedding = await self.embedding_service.embed(conversation.title)
        
        self._meeting_nodes[node.id] = node
        
        if self.knowledge_graph:
            self.knowledge_graph.add_node(
                node_id=node.id,
                node_type=RequirementNodeType.MEETING.value,
                properties={
                    "id": node.id,
                    "title": node.title,
                    "platform": node.platform,
                    "duration_minutes": node.duration_minutes,
                    "requirements_count": node.requirements_count,
                },
            )
        
        return node
    
    async def add_decision(
        self,
        segment: ConversationSegment,
        title: str,
        chosen_option: str,
        rationale: Optional[str] = None,
    ) -> DecisionNode:
        """Add a decision to the graph.
        
        Args:
            segment: Source segment
            title: Decision title
            chosen_option: The chosen option
            rationale: Reasoning behind decision
            
        Returns:
            Created decision node
        """
        node = DecisionNode(
            id=str(uuid.uuid4()),
            title=title,
            description=segment.text,
            chosen_option=chosen_option,
            rationale=rationale or "",
            source_conversation_id=segment.conversation_id,
            source_segment_id=segment.id,
            decision_makers=[segment.speaker],
        )
        
        if self.embedding_service:
            node.embedding = await self.embedding_service.embed(
                f"{title}. {segment.text}"
            )
        
        self._decision_nodes[node.id] = node
        
        if self.knowledge_graph:
            self.knowledge_graph.add_node(
                node_id=node.id,
                node_type=RequirementNodeType.DECISION.value,
                properties={
                    "id": node.id,
                    "title": node.title,
                    "chosen_option": node.chosen_option,
                },
            )
        
        return node
    
    async def get_or_create_stakeholder(
        self,
        name: str,
        tenant_id: str,
        email: Optional[str] = None,
        role: Optional[str] = None,
    ) -> StakeholderNode:
        """Get or create a stakeholder.
        
        Args:
            name: Stakeholder name
            tenant_id: Tenant ID
            email: Optional email
            role: Optional role
            
        Returns:
            Stakeholder node
        """
        # Check if exists (simple name matching)
        for node in self._stakeholder_nodes.values():
            if node.name.lower() == name.lower() and node.tenant_id == tenant_id:
                return node
        
        # Create new
        node = StakeholderNode(
            id=str(uuid.uuid4()),
            name=name,
            email=email,
            role=role or "",
            tenant_id=tenant_id,
        )
        
        self._stakeholder_nodes[node.id] = node
        
        if self.knowledge_graph:
            self.knowledge_graph.add_node(
                node_id=node.id,
                node_type=RequirementNodeType.STAKEHOLDER.value,
                properties={"id": node.id, "name": node.name, "role": node.role},
            )
        
        return node
    
    async def search_requirements(
        self,
        query: str,
        tenant_id: str,
        limit: int = 10,
    ) -> List[RequirementNode]:
        """Search requirements by semantic similarity.
        
        Args:
            query: Search query
            tenant_id: Tenant ID
            limit: Max results
            
        Returns:
            Matching requirement nodes
        """
        if not self.embedding_service:
            # Fallback to text matching
            return self._text_search_requirements(query, tenant_id, limit)
        
        query_embedding = await self.embedding_service.embed(query)
        
        # Calculate similarities
        scored = []
        for node in self._requirement_nodes.values():
            if node.tenant_id != tenant_id:
                continue
            if not node.embedding:
                continue
            
            similarity = self._cosine_similarity(query_embedding, node.embedding)
            scored.append((similarity, node))
        
        # Sort by similarity
        scored.sort(key=lambda x: x[0], reverse=True)
        
        return [node for _, node in scored[:limit]]
    
    def _text_search_requirements(
        self,
        query: str,
        tenant_id: str,
        limit: int,
    ) -> List[RequirementNode]:
        """Simple text-based search."""
        query_lower = query.lower()
        results = []
        
        for node in self._requirement_nodes.values():
            if node.tenant_id != tenant_id:
                continue
            
            score = 0
            if query_lower in node.title.lower():
                score += 2
            if query_lower in node.description.lower():
                score += 1
            for system in node.systems:
                if query_lower in system.lower():
                    score += 1
            
            if score > 0:
                results.append((score, node))
        
        results.sort(key=lambda x: x[0], reverse=True)
        return [node for _, node in results[:limit]]
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity."""
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)
    
    def get_requirements_for_service(
        self,
        service_id: str,
    ) -> List[RequirementNode]:
        """Get requirements affecting a service.
        
        Args:
            service_id: Service ID
            
        Returns:
            Requirements affecting the service
        """
        results = []
        for rel in self._relationships:
            if (
                rel.relationship_type == RequirementRelationType.AFFECTS
                and rel.target_id == service_id
            ):
                if rel.source_id in self._requirement_nodes:
                    results.append(self._requirement_nodes[rel.source_id])
        return results
    
    def get_requirements_from_meeting(
        self,
        meeting_id: str,
    ) -> List[RequirementNode]:
        """Get requirements derived from a meeting.
        
        Args:
            meeting_id: Meeting ID
            
        Returns:
            Requirements from the meeting
        """
        results = []
        for rel in self._relationships:
            if (
                rel.relationship_type == RequirementRelationType.DERIVED_FROM
                and rel.target_id == meeting_id
            ):
                if rel.source_id in self._requirement_nodes:
                    results.append(self._requirement_nodes[rel.source_id])
        return results
    
    def get_traceability_chain(
        self,
        requirement_id: str,
    ) -> Dict[str, Any]:
        """Get full traceability chain for a requirement.
        
        Args:
            requirement_id: Requirement ID
            
        Returns:
            Traceability information
        """
        req = self._requirement_nodes.get(requirement_id)
        if not req:
            return {}
        
        chain = {
            "requirement": req.to_dict(),
            "source_meeting": None,
            "affected_services": [],
            "stakeholders": [],
            "implementations": [],
        }
        
        # Find relationships
        for rel in self._relationships:
            if rel.source_id == requirement_id:
                if rel.relationship_type == RequirementRelationType.DERIVED_FROM:
                    meeting = self._meeting_nodes.get(rel.target_id)
                    if meeting:
                        chain["source_meeting"] = {
                            "id": meeting.id,
                            "title": meeting.title,
                            "platform": meeting.platform,
                        }
                elif rel.relationship_type == RequirementRelationType.AFFECTS:
                    chain["affected_services"].append(rel.target_id)
            
            elif rel.target_id == requirement_id:
                if rel.relationship_type == RequirementRelationType.REQUESTED:
                    stakeholder = self._stakeholder_nodes.get(rel.source_id)
                    if stakeholder:
                        chain["stakeholders"].append({
                            "id": stakeholder.id,
                            "name": stakeholder.name,
                            "role": stakeholder.role,
                        })
        
        return chain

