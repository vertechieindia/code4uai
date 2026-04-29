from __future__ import annotations
"""Audit logging for code4u.ai.

Security Controls:
- mTLS between services
- RBAC on intents
- Signed diffs
- Prompt + output logging (redacted)
- SOC2-ready logs
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import hashlib
import json
import structlog

logger = structlog.get_logger("security.audit")


class AuditEventType(str, Enum):
    """Types of audit events."""
    # Authentication
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_FAILED = "auth.failed"
    
    # Authorization
    AUTHZ_GRANTED = "authz.granted"
    AUTHZ_DENIED = "authz.denied"
    
    # Operations
    OP_REFACTOR = "op.refactor"
    OP_RENAME = "op.rename"
    OP_DELETE = "op.delete"
    OP_API_CHANGE = "op.api_change"
    OP_SCHEMA_CHANGE = "op.schema_change"
    
    # LLM
    LLM_REQUEST = "llm.request"
    LLM_RESPONSE = "llm.response"
    LLM_REJECTION = "llm.rejection"
    LLM_FALLBACK = "llm.fallback"
    
    # Security
    SEC_NO_AI_ZONE = "sec.no_ai_zone"
    SEC_BREAKING_CHANGE = "sec.breaking_change"
    SEC_CROSS_OWNER = "sec.cross_owner"
    
    # Data
    DATA_EXPORT = "data.export"
    DATA_ACCESS = "data.access"


@dataclass
class AuditEvent:
    """A single audit event."""
    event_id: str
    event_type: AuditEventType
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    # Context
    tenant_id: str = ""
    user_id: str = ""
    session_id: str = ""
    request_id: str = ""
    
    # Operation details
    operation: str = ""
    resource: str = ""
    outcome: str = ""  # success, failure, denied
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Redacted content (hashes, not raw)
    prompt_hash: Optional[str] = None
    response_hash: Optional[str] = None
    diff_hash: Optional[str] = None
    
    # Signature for integrity
    signature: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "request_id": self.request_id,
            "operation": self.operation,
            "resource": self.resource,
            "outcome": self.outcome,
            "metadata": self.metadata,
            "prompt_hash": self.prompt_hash,
            "response_hash": self.response_hash,
            "diff_hash": self.diff_hash,
            "signature": self.signature,
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class AuditLogger:
    """
    SOC2-ready audit logging.
    
    Features:
    - Immutable logs
    - Content hashing (no raw prompts/responses)
    - Event signing
    - Structured output
    """
    
    def __init__(self, signing_key: str = "audit-signing-key"):
        self._signing_key = signing_key
        self._event_counter = 0
    
    def log(
        self,
        event_type: AuditEventType,
        tenant_id: str = "",
        user_id: str = "",
        session_id: str = "",
        request_id: str = "",
        operation: str = "",
        resource: str = "",
        outcome: str = "success",
        metadata: Dict[str, Any] | None = None,
        prompt: Optional[str] = None,
        response: Optional[str] = None,
        diff: Optional[str] = None,
    ) -> AuditEvent:
        """
        Log an audit event.
        
        Content is hashed, not stored raw for security.
        """
        import uuid
        
        self._event_counter += 1
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        
        event = AuditEvent(
            event_id=event_id,
            event_type=event_type,
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            request_id=request_id,
            operation=operation,
            resource=resource,
            outcome=outcome,
            metadata=metadata or {},
        )
        
        # Hash content (never store raw prompts/responses)
        if prompt:
            event.prompt_hash = self._hash_content(prompt)
        if response:
            event.response_hash = self._hash_content(response)
        if diff:
            event.diff_hash = self._hash_content(diff)
        
        # Sign event for integrity
        event.signature = self._sign_event(event)
        
        # Log to structured logger
        logger.info(
            "audit_event",
            event_id=event.event_id,
            event_type=event.event_type.value,
            tenant_id=event.tenant_id,
            user_id=event.user_id,
            operation=event.operation,
            outcome=event.outcome,
        )
        
        return event
    
    def log_llm_request(
        self,
        tenant_id: str,
        user_id: str,
        request_id: str,
        prompt: str,
        model: str,
        metadata: Dict[str, Any] | None = None
    ) -> AuditEvent:
        """Log an LLM request."""
        return self.log(
            event_type=AuditEventType.LLM_REQUEST,
            tenant_id=tenant_id,
            user_id=user_id,
            request_id=request_id,
            operation="llm_generate",
            resource=model,
            prompt=prompt,
            metadata={
                **(metadata or {}),
                "model": model,
            }
        )
    
    def log_llm_response(
        self,
        tenant_id: str,
        user_id: str,
        request_id: str,
        response: str,
        model: str,
        tokens_used: int,
        latency_ms: float,
    ) -> AuditEvent:
        """Log an LLM response."""
        return self.log(
            event_type=AuditEventType.LLM_RESPONSE,
            tenant_id=tenant_id,
            user_id=user_id,
            request_id=request_id,
            operation="llm_generate",
            resource=model,
            outcome="success",
            response=response,
            metadata={
                "tokens_used": tokens_used,
                "latency_ms": latency_ms,
            }
        )
    
    def log_rejection(
        self,
        tenant_id: str,
        user_id: str,
        request_id: str,
        reason: str,
        is_hard: bool,
    ) -> AuditEvent:
        """Log an LLM rejection."""
        return self.log(
            event_type=AuditEventType.LLM_REJECTION,
            tenant_id=tenant_id,
            user_id=user_id,
            request_id=request_id,
            operation="llm_rejection",
            outcome="rejected",
            metadata={
                "reason": reason,
                "is_hard": is_hard,
            }
        )
    
    def log_no_ai_zone_violation(
        self,
        tenant_id: str,
        user_id: str,
        request_id: str,
        file_path: str,
        zone_name: str,
    ) -> AuditEvent:
        """Log a No-AI zone violation."""
        return self.log(
            event_type=AuditEventType.SEC_NO_AI_ZONE,
            tenant_id=tenant_id,
            user_id=user_id,
            request_id=request_id,
            operation="no_ai_zone_check",
            resource=file_path,
            outcome="blocked",
            metadata={
                "zone_name": zone_name,
            }
        )
    
    def log_breaking_change(
        self,
        tenant_id: str,
        user_id: str,
        request_id: str,
        affected_files: List[str],
        diff: str,
    ) -> AuditEvent:
        """Log a breaking change."""
        return self.log(
            event_type=AuditEventType.SEC_BREAKING_CHANGE,
            tenant_id=tenant_id,
            user_id=user_id,
            request_id=request_id,
            operation="breaking_change",
            outcome="flagged",
            diff=diff,
            metadata={
                "affected_file_count": len(affected_files),
                "affected_files": affected_files[:5],  # Limit for log size
            }
        )
    
    def _hash_content(self, content: str) -> str:
        """Hash content for audit storage."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _sign_event(self, event: AuditEvent) -> str:
        """Sign event for integrity verification."""
        content = json.dumps({
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "timestamp": event.timestamp,
            "tenant_id": event.tenant_id,
            "user_id": event.user_id,
            "outcome": event.outcome,
        }, sort_keys=True)
        
        signature_input = f"{self._signing_key}:{content}"
        return hashlib.sha256(signature_input.encode()).hexdigest()[:32]
    
    def verify_event(self, event: AuditEvent) -> bool:
        """Verify event signature."""
        expected_signature = self._sign_event(event)
        return event.signature == expected_signature

