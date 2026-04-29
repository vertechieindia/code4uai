from __future__ import annotations
"""No-AI Zones for code4u.ai.

You explicitly block AI from:
- Auth logic
- Payment flows
- Cryptography
- Compliance rules

This is a HUGE enterprise selling point.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import re
import structlog

logger = structlog.get_logger("security.no_ai_zones")


class NoAIZoneType(str, Enum):
    """Types of No-AI zones."""
    AUTH = "auth"           # Authentication/authorization
    PAYMENT = "payment"     # Payment processing
    CRYPTO = "crypto"       # Cryptographic operations
    COMPLIANCE = "compliance"  # Compliance/regulatory
    PII = "pii"             # Personal identifiable information
    SECRETS = "secrets"     # Secret management
    CUSTOM = "custom"       # Custom defined


@dataclass
class NoAIZone:
    """Definition of a No-AI zone."""
    zone_type: NoAIZoneType
    name: str
    description: str
    
    # Matching patterns
    path_patterns: List[str] = field(default_factory=list)
    content_patterns: List[str] = field(default_factory=list)
    symbol_patterns: List[str] = field(default_factory=list)
    
    # Severity
    is_hard_block: bool = True  # If True, completely block. If False, require approval.
    
    # Audit
    requires_justification: bool = True


# Predefined No-AI zones
DEFAULT_NO_AI_ZONES = [
    NoAIZone(
        zone_type=NoAIZoneType.AUTH,
        name="Authentication Logic",
        description="Authentication and authorization code",
        path_patterns=[
            r".*/auth/.*",
            r".*/authentication/.*",
            r".*/authorization/.*",
            r".*/login/.*",
            r".*/oauth/.*",
            r".*/jwt/.*",
            r".*/session/.*",
        ],
        content_patterns=[
            r"password",
            r"access_token",
            r"refresh_token",
            r"authenticate\(",
            r"authorize\(",
            r"verify_password",
            r"hash_password",
        ],
        symbol_patterns=[
            r"AuthService",
            r"AuthMiddleware",
            r"JWTHandler",
            r"SessionManager",
        ],
        is_hard_block=True,
    ),
    NoAIZone(
        zone_type=NoAIZoneType.PAYMENT,
        name="Payment Processing",
        description="Payment and billing code",
        path_patterns=[
            r".*/payment/.*",
            r".*/billing/.*",
            r".*/stripe/.*",
            r".*/checkout/.*",
            r".*/subscription/.*",
        ],
        content_patterns=[
            r"credit_card",
            r"card_number",
            r"stripe_key",
            r"payment_intent",
            r"charge\(",
            r"refund\(",
        ],
        symbol_patterns=[
            r"PaymentService",
            r"BillingService",
            r"StripeClient",
        ],
        is_hard_block=True,
    ),
    NoAIZone(
        zone_type=NoAIZoneType.CRYPTO,
        name="Cryptographic Operations",
        description="Encryption and cryptographic code",
        path_patterns=[
            r".*/crypto/.*",
            r".*/encryption/.*",
            r".*/security/.*",
        ],
        content_patterns=[
            r"private_key",
            r"secret_key",
            r"encrypt\(",
            r"decrypt\(",
            r"sign\(",
            r"verify\(",
            r"HMAC",
            r"AES",
            r"RSA",
        ],
        symbol_patterns=[
            r"CryptoService",
            r"EncryptionHandler",
            r"KeyManager",
        ],
        is_hard_block=True,
    ),
    NoAIZone(
        zone_type=NoAIZoneType.COMPLIANCE,
        name="Compliance Rules",
        description="Regulatory and compliance logic",
        path_patterns=[
            r".*/compliance/.*",
            r".*/gdpr/.*",
            r".*/hipaa/.*",
            r".*/pci/.*",
            r".*/audit/.*",
        ],
        content_patterns=[
            r"gdpr",
            r"hipaa",
            r"pci_dss",
            r"audit_log",
            r"data_retention",
            r"consent",
        ],
        symbol_patterns=[
            r"ComplianceChecker",
            r"AuditLogger",
            r"ConsentManager",
        ],
        is_hard_block=True,
    ),
    NoAIZone(
        zone_type=NoAIZoneType.SECRETS,
        name="Secret Management",
        description="Secret and credential management",
        path_patterns=[
            r".*/secrets/.*",
            r".*/vault/.*",
            r".*/credentials/.*",
        ],
        content_patterns=[
            r"api_key",
            r"api_secret",
            r"AWS_ACCESS_KEY",
            r"DATABASE_PASSWORD",
            r"\.env",
        ],
        symbol_patterns=[
            r"SecretManager",
            r"VaultClient",
            r"CredentialStore",
        ],
        is_hard_block=True,
    ),
]


@dataclass
class ZoneViolation:
    """A No-AI zone violation."""
    zone: NoAIZone
    file_path: str
    match_type: str  # path, content, symbol
    matched_pattern: str
    matched_text: Optional[str] = None


class NoAIZonePolicy:
    """
    Enforce No-AI zones.
    
    Blocks AI from modifying sensitive code areas.
    """
    
    def __init__(self, zones: list[NoAIZone] | None = None):
        self.zones = zones or list(DEFAULT_NO_AI_ZONES)
        self._compiled_patterns: dict[str, list[re.Pattern]] = {}
        self._compile_patterns()
    
    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for performance."""
        for zone in self.zones:
            zone_id = f"{zone.zone_type.value}:{zone.name}"
            self._compiled_patterns[zone_id] = {
                "path": [re.compile(p, re.IGNORECASE) for p in zone.path_patterns],
                "content": [re.compile(p, re.IGNORECASE) for p in zone.content_patterns],
                "symbol": [re.compile(p) for p in zone.symbol_patterns],
            }
    
    def add_zone(self, zone: NoAIZone) -> None:
        """Add a custom No-AI zone."""
        self.zones.append(zone)
        zone_id = f"{zone.zone_type.value}:{zone.name}"
        self._compiled_patterns[zone_id] = {
            "path": [re.compile(p, re.IGNORECASE) for p in zone.path_patterns],
            "content": [re.compile(p, re.IGNORECASE) for p in zone.content_patterns],
            "symbol": [re.compile(p) for p in zone.symbol_patterns],
        }
        
        logger.info("zone_added", zone_type=zone.zone_type.value, name=zone.name)
    
    def check_file(
        self,
        file_path: str,
        content: Optional[str] = None,
        symbols: List[str] | None = None
    ) -> list[ZoneViolation]:
        """
        Check if a file is in a No-AI zone.
        
        Returns list of violations.
        """
        violations = []
        
        for zone in self.zones:
            zone_id = f"{zone.zone_type.value}:{zone.name}"
            patterns = self._compiled_patterns.get(zone_id, {})
            
            # Check path patterns
            for pattern in patterns.get("path", []):
                if pattern.search(file_path):
                    violations.append(ZoneViolation(
                        zone=zone,
                        file_path=file_path,
                        match_type="path",
                        matched_pattern=pattern.pattern,
                    ))
                    break  # One violation per zone is enough
            
            # Check content patterns
            if content:
                for pattern in patterns.get("content", []):
                    match = pattern.search(content)
                    if match:
                        violations.append(ZoneViolation(
                            zone=zone,
                            file_path=file_path,
                            match_type="content",
                            matched_pattern=pattern.pattern,
                            matched_text=match.group()[:50],
                        ))
                        break
            
            # Check symbol patterns
            if symbols:
                for pattern in patterns.get("symbol", []):
                    for symbol in symbols:
                        if pattern.search(symbol):
                            violations.append(ZoneViolation(
                                zone=zone,
                                file_path=file_path,
                                match_type="symbol",
                                matched_pattern=pattern.pattern,
                                matched_text=symbol,
                            ))
                            break
        
        if violations:
            logger.warning(
                "no_ai_zone_violations",
                file_path=file_path,
                violation_count=len(violations),
                zones=[v.zone.name for v in violations]
            )
        
        return violations
    
    def check_files(
        self,
        files: list[Dict[str, Any]]
    ) -> dict[str, list[ZoneViolation]]:
        """
        Check multiple files for No-AI zone violations.
        
        Args:
            files: List of {"path": str, "content": str, "symbols": list}
        
        Returns:
            Dict mapping file paths to violations
        """
        all_violations = {}
        
        for file in files:
            path = file.get("path", "")
            content = file.get("content")
            symbols = file.get("symbols", [])
            
            violations = self.check_file(path, content, symbols)
            if violations:
                all_violations[path] = violations
        
        return all_violations
    
    def is_blocked(
        self,
        file_path: str,
        content: Optional[str] = None
    ) -> tuple[bool, str]:
        """
        Check if a file is hard-blocked from AI modification.
        
        Returns (is_blocked, reason).
        """
        violations = self.check_file(file_path, content)
        
        for v in violations:
            if v.zone.is_hard_block:
                return True, f"File is in No-AI zone: {v.zone.name}"
        
        return False, ""
    
    def get_zone_summary(self) -> list[Dict[str, Any]]:
        """Get summary of all No-AI zones."""
        return [
            {
                "type": zone.zone_type.value,
                "name": zone.name,
                "description": zone.description,
                "is_hard_block": zone.is_hard_block,
                "path_pattern_count": len(zone.path_patterns),
            }
            for zone in self.zones
        ]

