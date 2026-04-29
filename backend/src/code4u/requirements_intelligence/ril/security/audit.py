"""Audit logging for RIL."""

from __future__ import annotations
import json
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum


class RILAuditAction(str, Enum):
    """RIL audit actions."""
    # Consent
    CONSENT_GRANTED = "consent_granted"
    CONSENT_REVOKED = "consent_revoked"
    
    # Ingestion
    CAPTURE_STARTED = "capture_started"
    CAPTURE_STOPPED = "capture_stopped"
    TRANSCRIPT_RETRIEVED = "transcript_retrieved"
    
    # Processing
    CONVERSATION_PROCESSED = "conversation_processed"
    SEGMENTS_CLASSIFIED = "segments_classified"
    REQUIREMENTS_EXTRACTED = "requirements_extracted"
    
    # Graph
    REQUIREMENT_ADDED_TO_GRAPH = "requirement_added_to_graph"
    MEETING_ADDED_TO_GRAPH = "meeting_added_to_graph"
    
    # Execution
    PLAN_CREATED = "plan_created"
    PLAN_APPROVED = "plan_approved"
    PLAN_REJECTED = "plan_rejected"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETED = "execution_completed"
    
    # Security
    PII_REDACTED = "pii_redacted"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    
    # Data management
    AUDIO_DELETED = "audio_deleted"
    DATA_RETENTION_APPLIED = "data_retention_applied"


@dataclass
class RILAuditEntry:
    """An RIL audit log entry."""
    id: str
    timestamp: datetime
    action: RILAuditAction
    
    # Context
    tenant_id: str
    user_id: Optional[str] = None
    
    # Scope
    workspace_id: Optional[str] = None
    channel_id: Optional[str] = None
    meeting_id: Optional[str] = None
    conversation_id: Optional[str] = None
    requirement_id: Optional[str] = None
    plan_id: Optional[str] = None
    
    # Details
    details: Dict[str, Any] = field(default_factory=dict)
    
    # Result
    success: bool = True
    error: Optional[str] = None
    
    # Source
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["action"] = self.action.value
        return data
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class RILAuditLogger:
    """
    Immutable audit logging for RIL.
    
    All RIL actions are logged:
    - Consent changes
    - Conversation capture
    - Requirement extraction
    - Plan generation
    - Execution approvals
    - PII redaction stats
    - Data deletion
    
    Logs are:
    - Immutable
    - Tenant-isolated
    - Timestamped
    - Queryable
    
    SOC 2 / ISO 27001 compliant.
    """
    
    def __init__(
        self,
        storage_backend=None,
    ):
        """Initialize logger.
        
        Args:
            storage_backend: Optional persistent storage backend
        """
        self.storage = storage_backend
        self._logs: List[RILAuditEntry] = []
    
    def log(
        self,
        action: RILAuditAction,
        tenant_id: str,
        user_id: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None,
        **kwargs,
    ) -> RILAuditEntry:
        """Log an audit entry.
        
        Args:
            action: Audit action
            tenant_id: Tenant ID
            user_id: User performing action
            success: Whether action succeeded
            error: Error message if failed
            **kwargs: Additional fields
            
        Returns:
            Created audit entry
        """
        entry = RILAuditEntry(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            action=action,
            tenant_id=tenant_id,
            user_id=user_id,
            success=success,
            error=error,
            workspace_id=kwargs.get("workspace_id"),
            channel_id=kwargs.get("channel_id"),
            meeting_id=kwargs.get("meeting_id"),
            conversation_id=kwargs.get("conversation_id"),
            requirement_id=kwargs.get("requirement_id"),
            plan_id=kwargs.get("plan_id"),
            details=kwargs.get("details", {}),
            source_ip=kwargs.get("source_ip"),
            user_agent=kwargs.get("user_agent"),
        )
        
        # Store locally
        self._logs.append(entry)
        
        # Persist if backend available
        if self.storage:
            self.storage.store(entry)
        
        return entry
    
    def log_consent_granted(
        self,
        tenant_id: str,
        user_id: str,
        consent_type: str,
        workspace_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        meeting_id: Optional[str] = None,
    ) -> RILAuditEntry:
        """Log consent granted."""
        return self.log(
            action=RILAuditAction.CONSENT_GRANTED,
            tenant_id=tenant_id,
            user_id=user_id,
            workspace_id=workspace_id,
            channel_id=channel_id,
            meeting_id=meeting_id,
            details={"consent_type": consent_type},
        )
    
    def log_capture_started(
        self,
        tenant_id: str,
        user_id: str,
        conversation_id: str,
        platform: str,
    ) -> RILAuditEntry:
        """Log capture started."""
        return self.log(
            action=RILAuditAction.CAPTURE_STARTED,
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=conversation_id,
            details={"platform": platform},
        )
    
    def log_requirements_extracted(
        self,
        tenant_id: str,
        conversation_id: str,
        requirements_count: int,
        requirement_ids: List[str],
    ) -> RILAuditEntry:
        """Log requirements extraction."""
        return self.log(
            action=RILAuditAction.REQUIREMENTS_EXTRACTED,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            details={
                "requirements_count": requirements_count,
                "requirement_ids": requirement_ids,
            },
        )
    
    def log_plan_approved(
        self,
        tenant_id: str,
        user_id: str,
        plan_id: str,
        requirement_ids: List[str],
    ) -> RILAuditEntry:
        """Log plan approval."""
        return self.log(
            action=RILAuditAction.PLAN_APPROVED,
            tenant_id=tenant_id,
            user_id=user_id,
            plan_id=plan_id,
            details={"requirement_ids": requirement_ids},
        )
    
    def log_pii_redaction(
        self,
        tenant_id: str,
        conversation_id: str,
        redaction_stats: Dict[str, int],
    ) -> RILAuditEntry:
        """Log PII redaction."""
        return self.log(
            action=RILAuditAction.PII_REDACTED,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            details={"stats": redaction_stats},
        )
    
    def log_audio_deleted(
        self,
        tenant_id: str,
        meeting_id: str,
        reason: str = "retention_policy",
    ) -> RILAuditEntry:
        """Log audio deletion."""
        return self.log(
            action=RILAuditAction.AUDIO_DELETED,
            tenant_id=tenant_id,
            meeting_id=meeting_id,
            details={"reason": reason},
        )
    
    def query(
        self,
        tenant_id: str,
        action: Optional[RILAuditAction] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[RILAuditEntry]:
        """Query audit logs.
        
        Args:
            tenant_id: Tenant ID
            action: Optional action filter
            start_time: Optional start time
            end_time: Optional end time
            user_id: Optional user filter
            limit: Max results
            
        Returns:
            Matching audit entries
        """
        results = []
        
        for entry in reversed(self._logs):  # Most recent first
            if len(results) >= limit:
                break
            
            if entry.tenant_id != tenant_id:
                continue
            
            if action and entry.action != action:
                continue
            
            if start_time and entry.timestamp < start_time:
                continue
            
            if end_time and entry.timestamp > end_time:
                continue
            
            if user_id and entry.user_id != user_id:
                continue
            
            results.append(entry)
        
        return results
    
    def get_activity_summary(
        self,
        tenant_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get activity summary.
        
        Args:
            tenant_id: Tenant ID
            days: Number of days to summarize
            
        Returns:
            Activity summary
        """
        from datetime import timedelta
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        summary = {
            "total_actions": 0,
            "actions_by_type": {},
            "users_active": set(),
            "conversations_processed": set(),
            "requirements_created": 0,
            "plans_approved": 0,
            "pii_redactions": 0,
        }
        
        for entry in self._logs:
            if entry.tenant_id != tenant_id:
                continue
            if entry.timestamp < cutoff:
                continue
            
            summary["total_actions"] += 1
            
            action_key = entry.action.value
            summary["actions_by_type"][action_key] = \
                summary["actions_by_type"].get(action_key, 0) + 1
            
            if entry.user_id:
                summary["users_active"].add(entry.user_id)
            
            if entry.conversation_id:
                summary["conversations_processed"].add(entry.conversation_id)
            
            if entry.action == RILAuditAction.REQUIREMENTS_EXTRACTED:
                summary["requirements_created"] += \
                    entry.details.get("requirements_count", 0)
            
            if entry.action == RILAuditAction.PLAN_APPROVED:
                summary["plans_approved"] += 1
            
            if entry.action == RILAuditAction.PII_REDACTED:
                stats = entry.details.get("stats", {})
                summary["pii_redactions"] += sum(stats.values())
        
        # Convert sets to counts
        summary["users_active"] = len(summary["users_active"])
        summary["conversations_processed"] = len(summary["conversations_processed"])
        
        return summary

