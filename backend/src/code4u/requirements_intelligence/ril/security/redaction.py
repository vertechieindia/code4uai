"""PII redaction for RIL."""

from __future__ import annotations
import re
from typing import List, Dict, Any, Set, Tuple
from dataclasses import dataclass
from enum import Enum


class PIIType(str, Enum):
    """Types of PII."""
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    API_KEY = "api_key"
    PASSWORD = "password"
    NAME = "name"
    ADDRESS = "address"


@dataclass
class RedactionResult:
    """Result of PII redaction."""
    original_length: int
    redacted_length: int
    redactions: List[Dict[str, Any]]
    text: str


class PIIRedactor:
    """
    PII Redaction for conversation data.
    
    Automatically redacts:
    - Email addresses
    - Phone numbers
    - Social Security Numbers
    - Credit card numbers
    - IP addresses
    - API keys / tokens
    - Passwords (in context)
    
    Custom patterns can be added per tenant.
    """
    
    # Regex patterns for PII detection
    PATTERNS = {
        PIIType.EMAIL: r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        PIIType.PHONE: r'\b(?:\+1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b',
        PIIType.SSN: r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b',
        PIIType.CREDIT_CARD: r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
        PIIType.IP_ADDRESS: r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
        PIIType.API_KEY: r'\b(?:sk|pk|api|key|token|secret|bearer)[-_]?[a-zA-Z0-9]{16,}\b',
        PIIType.PASSWORD: r'(?i)(?:password|pwd|passwd|secret|token)[\s:=]+[^\s]{4,}',
    }
    
    # Replacement templates
    REPLACEMENTS = {
        PIIType.EMAIL: "[EMAIL REDACTED]",
        PIIType.PHONE: "[PHONE REDACTED]",
        PIIType.SSN: "[SSN REDACTED]",
        PIIType.CREDIT_CARD: "[CARD REDACTED]",
        PIIType.IP_ADDRESS: "[IP REDACTED]",
        PIIType.API_KEY: "[API KEY REDACTED]",
        PIIType.PASSWORD: "[PASSWORD REDACTED]",
        PIIType.NAME: "[NAME REDACTED]",
        PIIType.ADDRESS: "[ADDRESS REDACTED]",
    }
    
    def __init__(
        self,
        enabled_types: List[PIIType] = None,
        custom_patterns: Dict[str, str] = None,
    ):
        """Initialize redactor.
        
        Args:
            enabled_types: PII types to redact (all if None)
            custom_patterns: Additional regex patterns
        """
        self.enabled_types = enabled_types or list(PIIType)
        self.custom_patterns = custom_patterns or {}
        
        # Compile patterns
        self._compiled: Dict[str, re.Pattern] = {}
        for pii_type in self.enabled_types:
            if pii_type in self.PATTERNS:
                self._compiled[pii_type.value] = re.compile(
                    self.PATTERNS[pii_type],
                    re.IGNORECASE,
                )
        
        for name, pattern in self.custom_patterns.items():
            self._compiled[name] = re.compile(pattern, re.IGNORECASE)
    
    def redact(self, text: str) -> RedactionResult:
        """Redact PII from text.
        
        Args:
            text: Text to redact
            
        Returns:
            Redaction result with redacted text
        """
        original_length = len(text)
        redactions = []
        redacted = text
        
        for pii_type_str, pattern in self._compiled.items():
            try:
                pii_type = PIIType(pii_type_str)
                replacement = self.REPLACEMENTS.get(pii_type, "[REDACTED]")
            except ValueError:
                replacement = f"[{pii_type_str.upper()} REDACTED]"
            
            for match in pattern.finditer(redacted):
                redactions.append({
                    "type": pii_type_str,
                    "start": match.start(),
                    "end": match.end(),
                    "original_length": match.end() - match.start(),
                })
            
            redacted = pattern.sub(replacement, redacted)
        
        return RedactionResult(
            original_length=original_length,
            redacted_length=len(redacted),
            redactions=redactions,
            text=redacted,
        )
    
    def redact_batch(self, texts: List[str]) -> List[RedactionResult]:
        """Redact PII from multiple texts.
        
        Args:
            texts: List of texts
            
        Returns:
            List of redaction results
        """
        return [self.redact(text) for text in texts]
    
    def detect_only(self, text: str) -> List[Dict[str, Any]]:
        """Detect PII without redacting.
        
        Args:
            text: Text to scan
            
        Returns:
            List of PII detections
        """
        detections = []
        
        for pii_type_str, pattern in self._compiled.items():
            for match in pattern.finditer(text):
                detections.append({
                    "type": pii_type_str,
                    "start": match.start(),
                    "end": match.end(),
                    "text": match.group()[:3] + "..." if len(match.group()) > 6 else "***",
                })
        
        return detections
    
    def redact_conversation(
        self,
        messages: List[Dict[str, Any]],
        text_field: str = "text",
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Redact PII from conversation messages.
        
        Args:
            messages: List of message dicts
            text_field: Field name containing text
            
        Returns:
            Tuple of (redacted messages, total redaction count)
        """
        redacted_messages = []
        total_redactions = 0
        
        for msg in messages:
            msg_copy = msg.copy()
            
            if text_field in msg_copy:
                result = self.redact(msg_copy[text_field])
                msg_copy[text_field] = result.text
                total_redactions += len(result.redactions)
            
            redacted_messages.append(msg_copy)
        
        return redacted_messages, total_redactions
    
    def add_custom_pattern(
        self,
        name: str,
        pattern: str,
        replacement: str = None,
    ) -> None:
        """Add a custom PII pattern.
        
        Args:
            name: Pattern name
            pattern: Regex pattern
            replacement: Optional replacement text
        """
        self._compiled[name] = re.compile(pattern, re.IGNORECASE)
        self.custom_patterns[name] = pattern
    
    def get_redaction_stats(
        self,
        results: List[RedactionResult],
    ) -> Dict[str, int]:
        """Get statistics from redaction results.
        
        Args:
            results: List of redaction results
            
        Returns:
            Stats by PII type
        """
        stats: Dict[str, int] = {}
        
        for result in results:
            for redaction in result.redactions:
                pii_type = redaction["type"]
                stats[pii_type] = stats.get(pii_type, 0) + 1
        
        return stats

