"""Consent management for RIL."""

from __future__ import annotations
import uuid
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ConsentType(str, Enum):
    """Types of consent."""
    WORKSPACE = "workspace"     # Workspace-level opt-in
    CHANNEL = "channel"         # Channel-level consent
    MEETING = "meeting"         # Per-meeting consent
    AUDIO = "audio"            # Audio recording consent
    TRANSCRIPTION = "transcription"  # Transcription consent
    AI_PROCESSING = "ai_processing"  # AI/LLM processing consent


class ConsentStatus(str, Enum):
    """Consent status."""
    GRANTED = "granted"
    DENIED = "denied"
    PENDING = "pending"
    REVOKED = "revoked"


@dataclass
class ConsentRecord:
    """A consent record."""
    id: str
    tenant_id: str
    type: ConsentType
    status: ConsentStatus
    
    # Scope
    workspace_id: Optional[str] = None
    channel_id: Optional[str] = None
    meeting_id: Optional[str] = None
    user_id: Optional[str] = None
    
    # Details
    granted_by: Optional[str] = None
    granted_at: Optional[datetime] = None
    revoked_by: Optional[str] = None
    revoked_at: Optional[datetime] = None
    
    # Expiration
    expires_at: Optional[datetime] = None
    
    # Audit
    created_at: datetime = field(default_factory=datetime.utcnow)


class ConsentManager:
    """
    Manages consent for RIL features.
    
    Key rules:
    - Workspace must opt-in first
    - Channels can be opted-in/out individually
    - Meetings require explicit consent
    - Audio recording requires separate consent
    - All consent is revocable
    """
    
    def __init__(self):
        """Initialize consent manager."""
        self._consents: Dict[str, ConsentRecord] = {}
        self._workspace_consents: Dict[str, Set[ConsentType]] = {}
        self._channel_consents: Dict[str, Set[ConsentType]] = {}
        self._meeting_consents: Dict[str, Set[ConsentType]] = {}
    
    def grant_workspace_consent(
        self,
        tenant_id: str,
        workspace_id: str,
        consent_types: List[ConsentType],
        granted_by: str,
        expires_at: Optional[datetime] = None,
    ) -> List[ConsentRecord]:
        """Grant workspace-level consent.
        
        Args:
            tenant_id: Tenant ID
            workspace_id: Workspace ID
            consent_types: Types of consent to grant
            granted_by: User granting consent
            expires_at: Optional expiration
            
        Returns:
            Created consent records
        """
        records = []
        
        for ctype in consent_types:
            record = ConsentRecord(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                type=ctype,
                status=ConsentStatus.GRANTED,
                workspace_id=workspace_id,
                granted_by=granted_by,
                granted_at=datetime.utcnow(),
                expires_at=expires_at,
            )
            
            self._consents[record.id] = record
            
            # Update index
            key = f"{tenant_id}:{workspace_id}"
            if key not in self._workspace_consents:
                self._workspace_consents[key] = set()
            self._workspace_consents[key].add(ctype)
            
            records.append(record)
        
        return records
    
    def grant_channel_consent(
        self,
        tenant_id: str,
        channel_id: str,
        consent_types: List[ConsentType],
        granted_by: str,
    ) -> List[ConsentRecord]:
        """Grant channel-level consent.
        
        Args:
            tenant_id: Tenant ID
            channel_id: Channel ID
            consent_types: Types of consent
            granted_by: User granting
            
        Returns:
            Consent records
        """
        records = []
        
        for ctype in consent_types:
            record = ConsentRecord(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                type=ctype,
                status=ConsentStatus.GRANTED,
                channel_id=channel_id,
                granted_by=granted_by,
                granted_at=datetime.utcnow(),
            )
            
            self._consents[record.id] = record
            
            key = f"{tenant_id}:{channel_id}"
            if key not in self._channel_consents:
                self._channel_consents[key] = set()
            self._channel_consents[key].add(ctype)
            
            records.append(record)
        
        return records
    
    def grant_meeting_consent(
        self,
        tenant_id: str,
        meeting_id: str,
        consent_types: List[ConsentType],
        granted_by: str,
        participants: Optional[List[str]] = None,
    ) -> List[ConsentRecord]:
        """Grant per-meeting consent.
        
        Args:
            tenant_id: Tenant ID
            meeting_id: Meeting ID
            consent_types: Types of consent
            granted_by: User granting
            participants: Optional list of consenting participants
            
        Returns:
            Consent records
        """
        records = []
        
        for ctype in consent_types:
            record = ConsentRecord(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                type=ctype,
                status=ConsentStatus.GRANTED,
                meeting_id=meeting_id,
                granted_by=granted_by,
                granted_at=datetime.utcnow(),
            )
            
            self._consents[record.id] = record
            
            key = f"{tenant_id}:{meeting_id}"
            if key not in self._meeting_consents:
                self._meeting_consents[key] = set()
            self._meeting_consents[key].add(ctype)
            
            records.append(record)
        
        return records
    
    def revoke_consent(
        self,
        consent_id: str,
        revoked_by: str,
    ) -> bool:
        """Revoke a consent.
        
        Args:
            consent_id: Consent record ID
            revoked_by: User revoking
            
        Returns:
            True if revoked
        """
        record = self._consents.get(consent_id)
        if not record:
            return False
        
        record.status = ConsentStatus.REVOKED
        record.revoked_by = revoked_by
        record.revoked_at = datetime.utcnow()
        
        # Update indices
        if record.workspace_id:
            key = f"{record.tenant_id}:{record.workspace_id}"
            if key in self._workspace_consents:
                self._workspace_consents[key].discard(record.type)
        
        if record.channel_id:
            key = f"{record.tenant_id}:{record.channel_id}"
            if key in self._channel_consents:
                self._channel_consents[key].discard(record.type)
        
        if record.meeting_id:
            key = f"{record.tenant_id}:{record.meeting_id}"
            if key in self._meeting_consents:
                self._meeting_consents[key].discard(record.type)
        
        return True
    
    def check_consent(
        self,
        tenant_id: str,
        consent_type: ConsentType,
        workspace_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        meeting_id: Optional[str] = None,
    ) -> bool:
        """Check if consent is granted.
        
        Checks in order:
        1. Meeting-level consent (most specific)
        2. Channel-level consent
        3. Workspace-level consent (most general)
        
        Args:
            tenant_id: Tenant ID
            consent_type: Type to check
            workspace_id: Optional workspace
            channel_id: Optional channel
            meeting_id: Optional meeting
            
        Returns:
            True if consent is granted
        """
        # Check meeting consent first (most specific)
        if meeting_id:
            key = f"{tenant_id}:{meeting_id}"
            if key in self._meeting_consents:
                if consent_type in self._meeting_consents[key]:
                    return True
        
        # Check channel consent
        if channel_id:
            key = f"{tenant_id}:{channel_id}"
            if key in self._channel_consents:
                if consent_type in self._channel_consents[key]:
                    return True
        
        # Check workspace consent (most general)
        if workspace_id:
            key = f"{tenant_id}:{workspace_id}"
            if key in self._workspace_consents:
                if consent_type in self._workspace_consents[key]:
                    return True
        
        return False
    
    def check_all_consents(
        self,
        tenant_id: str,
        consent_types: List[ConsentType],
        workspace_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        meeting_id: Optional[str] = None,
    ) -> Dict[ConsentType, bool]:
        """Check multiple consent types.
        
        Args:
            tenant_id: Tenant ID
            consent_types: Types to check
            workspace_id: Optional workspace
            channel_id: Optional channel
            meeting_id: Optional meeting
            
        Returns:
            Dict of type -> granted status
        """
        return {
            ctype: self.check_consent(
                tenant_id, ctype, workspace_id, channel_id, meeting_id
            )
            for ctype in consent_types
        }
    
    def get_required_consents_for_feature(
        self,
        feature: str,
    ) -> List[ConsentType]:
        """Get required consents for a feature.
        
        Args:
            feature: Feature name
            
        Returns:
            Required consent types
        """
        feature_consents = {
            "channel_capture": [ConsentType.WORKSPACE, ConsentType.CHANNEL],
            "meeting_transcription": [
                ConsentType.WORKSPACE,
                ConsentType.MEETING,
                ConsentType.TRANSCRIPTION,
            ],
            "audio_recording": [
                ConsentType.WORKSPACE,
                ConsentType.MEETING,
                ConsentType.AUDIO,
            ],
            "requirement_extraction": [
                ConsentType.WORKSPACE,
                ConsentType.AI_PROCESSING,
            ],
            "agent_execution": [
                ConsentType.WORKSPACE,
                ConsentType.AI_PROCESSING,
            ],
        }
        
        return feature_consents.get(feature, [ConsentType.WORKSPACE])

