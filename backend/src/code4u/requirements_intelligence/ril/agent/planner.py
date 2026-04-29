"""Requirement to execution plan conversion."""

from __future__ import annotations
import json
import uuid
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..models import StructuredRequirement, RequirementType


class PlanType(str, Enum):
    """Types of plans."""
    PRD = "prd"
    TECHNICAL = "technical"
    IMPLEMENTATION = "implementation"
    SPIKE = "spike"


class PlanStatus(str, Enum):
    """Plan status."""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass
class ImplementationTask:
    """A single implementation task."""
    id: str
    title: str
    description: str
    
    # Assignment
    assigned_service: Optional[str] = None
    assigned_team: Optional[str] = None
    
    # Effort
    estimated_hours: Optional[float] = None
    complexity: str = "medium"  # low, medium, high
    
    # Dependencies
    depends_on: List[str] = field(default_factory=list)
    
    # Status
    status: str = "pending"


@dataclass
class ExecutionPlan:
    """An execution plan for requirements."""
    id: str
    type: PlanType
    status: PlanStatus = PlanStatus.DRAFT
    
    # Source requirements
    requirement_ids: List[str] = field(default_factory=list)
    
    # Plan content
    title: str = ""
    summary: str = ""
    
    # PRD fields
    problem_statement: str = ""
    proposed_solution: str = ""
    success_metrics: List[str] = field(default_factory=list)
    out_of_scope: List[str] = field(default_factory=list)
    
    # Technical fields
    architecture_changes: List[str] = field(default_factory=list)
    services_affected: List[str] = field(default_factory=list)
    api_changes: List[Dict[str, Any]] = field(default_factory=list)
    database_changes: List[Dict[str, Any]] = field(default_factory=list)
    
    # Implementation tasks
    tasks: List[ImplementationTask] = field(default_factory=list)
    
    # Estimates
    total_estimated_hours: float = 0.0
    estimated_completion: Optional[datetime] = None
    
    # Risk assessment
    risks: List[Dict[str, str]] = field(default_factory=list)
    
    # Approval
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "status": self.status.value,
            "title": self.title,
            "summary": self.summary,
            "requirement_ids": self.requirement_ids,
            "services_affected": self.services_affected,
            "tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "service": t.assigned_service,
                    "hours": t.estimated_hours,
                    "status": t.status,
                }
                for t in self.tasks
            ],
            "total_hours": self.total_estimated_hours,
            "created_at": self.created_at.isoformat(),
        }


TECHNICAL_PLAN_PROMPT = """You are a senior software architect.

Convert these requirements into a technical implementation plan.

REQUIREMENTS:
{requirements}

AFFECTED SYSTEMS (from Knowledge Graph):
{systems}

Generate a technical plan in JSON format:
{{
  "title": "Plan title",
  "summary": "2-3 sentence summary",
  "architecture_changes": ["List of architecture changes"],
  "services_affected": ["List of services to modify"],
  "api_changes": [
    {{"service": "...", "endpoint": "...", "change": "..."}}
  ],
  "database_changes": [
    {{"service": "...", "change": "...", "migration_required": true/false}}
  ],
  "tasks": [
    {{
      "id": "TASK-001",
      "title": "Task title",
      "description": "What needs to be done",
      "assigned_service": "service name",
      "estimated_hours": 4,
      "complexity": "low|medium|high",
      "depends_on": []
    }}
  ],
  "risks": [
    {{"risk": "...", "mitigation": "...", "severity": "low|medium|high"}}
  ]
}}

JSON only:"""


class RequirementPlanner:
    """
    Converts requirements into execution plans.
    
    Supports:
    - PRD generation
    - Technical plan generation
    - Implementation task breakdown
    """
    
    def __init__(
        self,
        knowledge_graph=None,
        llm_client=None,
    ):
        """Initialize planner.
        
        Args:
            knowledge_graph: Knowledge graph for service mapping
            llm_client: LLM client for plan generation
        """
        self.knowledge_graph = knowledge_graph
        self.llm_client = llm_client
        self._plans: Dict[str, ExecutionPlan] = {}
    
    async def create_technical_plan(
        self,
        requirements: List[StructuredRequirement],
        created_by: str = "system",
    ) -> ExecutionPlan:
        """Create a technical implementation plan.
        
        Args:
            requirements: Requirements to plan
            created_by: User creating the plan
            
        Returns:
            Execution plan
        """
        # Collect all affected systems
        systems = set()
        for req in requirements:
            systems.update(req.systems)
            systems.update(req.services)
        
        # Generate plan with LLM if available
        if self.llm_client:
            plan = await self._generate_plan_llm(
                requirements,
                list(systems),
                PlanType.TECHNICAL,
            )
        else:
            plan = self._generate_plan_rule_based(
                requirements,
                list(systems),
                PlanType.TECHNICAL,
            )
        
        plan.created_by = created_by
        plan.requirement_ids = [r.id for r in requirements]
        
        # Store plan
        self._plans[plan.id] = plan
        
        return plan
    
    async def create_prd(
        self,
        requirements: List[StructuredRequirement],
        created_by: str = "system",
    ) -> ExecutionPlan:
        """Create a Product Requirements Document.
        
        Args:
            requirements: Requirements for PRD
            created_by: User creating the PRD
            
        Returns:
            PRD as ExecutionPlan
        """
        plan = ExecutionPlan(
            id=str(uuid.uuid4()),
            type=PlanType.PRD,
            requirement_ids=[r.id for r in requirements],
            created_by=created_by,
        )
        
        # Aggregate problem statement
        plan.problem_statement = self._aggregate_descriptions(requirements)
        
        # Generate title
        if requirements:
            plan.title = f"PRD: {requirements[0].title}"
            if len(requirements) > 1:
                plan.title += f" (+{len(requirements)-1} more)"
        
        # Collect constraints as out of scope
        for req in requirements:
            plan.out_of_scope.extend(req.constraints)
        
        # Collect acceptance criteria as success metrics
        for req in requirements:
            plan.success_metrics.extend(req.acceptance_criteria)
        
        self._plans[plan.id] = plan
        return plan
    
    async def _generate_plan_llm(
        self,
        requirements: List[StructuredRequirement],
        systems: List[str],
        plan_type: PlanType,
    ) -> ExecutionPlan:
        """Generate plan using LLM."""
        # Format requirements
        req_texts = []
        for req in requirements:
            req_texts.append(
                f"[{req.id}] {req.title}\n"
                f"  Type: {req.type.value}\n"
                f"  Priority: {req.priority.value}\n"
                f"  Description: {req.description}\n"
                f"  Systems: {', '.join(req.systems)}\n"
                f"  Constraints: {', '.join(req.constraints)}"
            )
        
        prompt = TECHNICAL_PLAN_PROMPT.format(
            requirements="\n\n".join(req_texts),
            systems=", ".join(systems) or "None specified",
        )
        
        try:
            response = await self._call_llm(prompt)
            data = json.loads(response)
            
            # Parse response into plan
            plan = ExecutionPlan(
                id=str(uuid.uuid4()),
                type=plan_type,
                title=data.get("title", "Implementation Plan"),
                summary=data.get("summary", ""),
                architecture_changes=data.get("architecture_changes", []),
                services_affected=data.get("services_affected", systems),
                api_changes=data.get("api_changes", []),
                database_changes=data.get("database_changes", []),
                risks=data.get("risks", []),
            )
            
            # Parse tasks
            for task_data in data.get("tasks", []):
                task = ImplementationTask(
                    id=task_data.get("id", str(uuid.uuid4())),
                    title=task_data.get("title", ""),
                    description=task_data.get("description", ""),
                    assigned_service=task_data.get("assigned_service"),
                    estimated_hours=task_data.get("estimated_hours"),
                    complexity=task_data.get("complexity", "medium"),
                    depends_on=task_data.get("depends_on", []),
                )
                plan.tasks.append(task)
            
            # Calculate totals
            plan.total_estimated_hours = sum(
                t.estimated_hours or 0 for t in plan.tasks
            )
            
            return plan
            
        except Exception:
            # Fall back to rule-based
            return self._generate_plan_rule_based(
                requirements, systems, plan_type
            )
    
    def _generate_plan_rule_based(
        self,
        requirements: List[StructuredRequirement],
        systems: List[str],
        plan_type: PlanType,
    ) -> ExecutionPlan:
        """Generate plan using rule-based approach."""
        plan = ExecutionPlan(
            id=str(uuid.uuid4()),
            type=plan_type,
            services_affected=systems,
        )
        
        if requirements:
            plan.title = f"Implementation: {requirements[0].title}"
        
        plan.summary = self._aggregate_descriptions(requirements)
        
        # Generate tasks per service
        task_counter = 1
        for system in systems:
            # Find requirements affecting this system
            system_reqs = [
                r for r in requirements
                if system in r.systems or system in r.services
            ]
            
            if system_reqs:
                task = ImplementationTask(
                    id=f"TASK-{task_counter:03d}",
                    title=f"Update {system} for new requirements",
                    description=f"Implement changes in {system}: " + 
                        ", ".join(r.title for r in system_reqs[:3]),
                    assigned_service=system,
                    estimated_hours=8.0 * len(system_reqs),
                    complexity="medium",
                )
                plan.tasks.append(task)
                task_counter += 1
        
        plan.total_estimated_hours = sum(
            t.estimated_hours or 0 for t in plan.tasks
        )
        
        return plan
    
    def _aggregate_descriptions(
        self,
        requirements: List[StructuredRequirement],
    ) -> str:
        """Aggregate requirement descriptions."""
        descriptions = [r.description for r in requirements if r.description]
        return " | ".join(descriptions[:5])
    
    def get_plan(self, plan_id: str) -> Optional[ExecutionPlan]:
        """Get a plan by ID."""
        return self._plans.get(plan_id)
    
    def approve_plan(
        self,
        plan_id: str,
        approved_by: str,
    ) -> bool:
        """Approve a plan for execution.
        
        Args:
            plan_id: Plan ID
            approved_by: User approving
            
        Returns:
            True if approved
        """
        plan = self._plans.get(plan_id)
        if not plan:
            return False
        
        plan.status = PlanStatus.APPROVED
        plan.approved_by = approved_by
        plan.approved_at = datetime.utcnow()
        
        return True
    
    def reject_plan(
        self,
        plan_id: str,
        reason: str,
    ) -> bool:
        """Reject a plan.
        
        Args:
            plan_id: Plan ID
            reason: Rejection reason
            
        Returns:
            True if rejected
        """
        plan = self._plans.get(plan_id)
        if not plan:
            return False
        
        plan.status = PlanStatus.REJECTED
        return True
    
    async def _call_llm(self, prompt: str) -> str:
        """Call LLM."""
        if hasattr(self.llm_client, 'complete'):
            return await self.llm_client.complete(
                prompt=prompt,
                temperature=0.0,
                max_tokens=2000,
            )
        
        import os
        import httpx
        
        api_key = os.getenv("OPENAI_API_KEY", "")
        base_url = os.getenv("LLM_API_URL", "https://api.openai.com/v1")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                    "max_tokens": 2000,
                },
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

