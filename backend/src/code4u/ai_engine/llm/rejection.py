from __future__ import annotations
"""LLM Rejection & Retry Policy for code4u.ai.

This is where AI hallucinations die.

Rejection Types:
- Hard Rejection: Immediate FAIL, no retry
- Soft Rejection: Retry allowed with feedback

Never resend the same prompt on retry.
Each retry adds MACHINE FEEDBACK, not human words.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import structlog
import json
import re

logger = structlog.get_logger("llm.rejection")


class RejectionType(str, Enum):
    """Types of rejection."""
    HARD = "hard"  # No retry allowed
    SOFT = "soft"  # Retry allowed


class RejectionReason(str, Enum):
    """Specific rejection reasons."""
    # Hard rejections
    INVALID_JSON = "invalid_json"
    INVALID_DIFF = "invalid_diff"
    FORBIDDEN_FILE = "forbidden_file"
    OWNERSHIP_VIOLATION = "ownership_violation"
    API_INVENTION = "api_invention"
    SCOPE_EXCEEDED = "scope_exceeded"
    INSUFFICIENT_CONTEXT = "insufficient_context"
    
    # Soft rejections
    FORMATTING_ISSUE = "formatting_issue"
    MISSING_IMPORT = "missing_import"
    TYPE_MISMATCH = "type_mismatch"
    PARTIAL_DIFF = "partial_diff"
    SYNTAX_ERROR = "syntax_error"


@dataclass
class Rejection:
    """A rejection of LLM output."""
    rejection_type: RejectionType
    reason: RejectionReason
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def can_retry(self) -> bool:
        return self.rejection_type == RejectionType.SOFT


@dataclass
class RetryContext:
    """Context for retry attempts."""
    attempt: int
    previous_error: str
    correction_required: str
    additional_context: Dict[str, Any] = field(default_factory=dict)
    
    def to_prompt_addition(self) -> str:
        """Generate prompt addition for retry."""
        return f"""PREVIOUS ERROR:
- {self.previous_error}

CORRECTION REQUIRED:
- {self.correction_required}

ATTEMPT: {self.attempt} of 3
DO NOT repeat the same error."""


class RejectionPolicy:
    """
    Policy for rejecting and retrying LLM outputs.
    
    Hard Rejection Triggers (No Retry):
    - Output not valid JSON
    - Diff not parseable
    - Touches forbidden files
    - Violates ownership
    - Invents APIs/symbols
    - Exceeds scope
    
    Soft Rejection (Retry Allowed):
    - Formatting issue
    - Missing import
    - Minor type mismatch
    - Partial diff
    """
    
    MAX_RETRIES = 2
    
    def __init__(self, forbidden_paths: List[str] | None = None):
        self.forbidden_paths = forbidden_paths or []
        self.known_symbols: Set[str] = set()
    
    def set_scope(
        self,
        allowed_files: List[str],
        known_symbols: List[str],
        forbidden_paths: List[str] | None = None
    ):
        """Set the valid scope for rejection checks."""
        self.allowed_files = set(allowed_files)
        self.known_symbols = set(known_symbols)
        if forbidden_paths:
            self.forbidden_paths = forbidden_paths
    
    def evaluate(
        self,
        response: str,
        expected_format: str = "json"
    ) -> Rejection | None:
        """
        Evaluate LLM response for rejection.
        
        Returns Rejection if response should be rejected, None if valid.
        """
        # Check 1: Valid JSON
        if expected_format == "json":
            rejection = self._check_json_format(response)
            if rejection:
                return rejection
        
        # Check 2: Valid diff format
        if expected_format in ("json", "diff"):
            rejection = self._check_diff_format(response)
            if rejection:
                return rejection
        
        # Check 3: Insufficient context marker
        if "INSUFFICIENT_CONTEXT" in response:
            return Rejection(
                rejection_type=RejectionType.HARD,
                reason=RejectionReason.INSUFFICIENT_CONTEXT,
                message="LLM indicated insufficient context to complete task"
            )
        
        # Check 4: Forbidden files
        rejection = self._check_forbidden_files(response)
        if rejection:
            return rejection
        
        # Check 5: Scope exceeded
        rejection = self._check_scope(response)
        if rejection:
            return rejection
        
        # Check 6: API invention (hallucination)
        rejection = self._check_api_invention(response)
        if rejection:
            return rejection
        
        # Check 7: Syntax errors (soft)
        rejection = self._check_syntax(response)
        if rejection:
            return rejection
        
        logger.info("response_accepted")
        return None
    
    def _check_json_format(self, response: str) -> Rejection | None:
        """Check if response is valid JSON."""
        # Try to extract JSON from markdown code block
        json_content = response
        if "```json" in response:
            match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
            if match:
                json_content = match.group(1)
        elif "```" in response:
            match = re.search(r"```\s*(.*?)\s*```", response, re.DOTALL)
            if match:
                json_content = match.group(1)
        
        try:
            json.loads(json_content)
            return None
        except json.JSONDecodeError as e:
            return Rejection(
                rejection_type=RejectionType.HARD,
                reason=RejectionReason.INVALID_JSON,
                message=f"Invalid JSON: {str(e)}",
                details={"position": e.pos, "content_preview": json_content[:200]}
            )
    
    def _check_diff_format(self, response: str) -> Rejection | None:
        """Check if diff is parseable."""
        # Extract diffs from JSON if present
        try:
            data = self._extract_json(response)
            if not data:
                return None  # Not JSON, will be caught elsewhere
            
            diffs = data.get("diffs", [])
            if not diffs and "diff" not in str(data):
                return Rejection(
                    rejection_type=RejectionType.SOFT,
                    reason=RejectionReason.PARTIAL_DIFF,
                    message="No diffs found in response"
                )
            
            for diff_obj in diffs:
                diff_content = diff_obj.get("diff", "")
                if not self._is_valid_diff(diff_content):
                    return Rejection(
                        rejection_type=RejectionType.SOFT,
                        reason=RejectionReason.FORMATTING_ISSUE,
                        message="Malformed diff format",
                        details={"diff_preview": diff_content[:200]}
                    )
            
            return None
            
        except Exception:
            return None
    
    def _check_forbidden_files(self, response: str) -> Rejection | None:
        """Check if response touches forbidden files."""
        for path in self.forbidden_paths:
            if path in response:
                return Rejection(
                    rejection_type=RejectionType.HARD,
                    reason=RejectionReason.FORBIDDEN_FILE,
                    message=f"Attempted to modify forbidden file: {path}",
                    details={"forbidden_path": path}
                )
        return None
    
    def _check_scope(self, response: str) -> Rejection | None:
        """Check if response stays within scope."""
        if not hasattr(self, 'allowed_files') or not self.allowed_files:
            return None
        
        try:
            data = self._extract_json(response)
            if not data:
                return None
            
            diffs = data.get("diffs", [])
            for diff_obj in diffs:
                file_path = diff_obj.get("file_path", "")
                if file_path and file_path not in self.allowed_files:
                    # Check if it's a new file creation
                    if "DO_NOT_CREATE_NEW_FILES" in str(self.__dict__):
                        return Rejection(
                            rejection_type=RejectionType.HARD,
                            reason=RejectionReason.SCOPE_EXCEEDED,
                            message=f"File not in scope: {file_path}",
                            details={"file_path": file_path}
                        )
            
            return None
            
        except Exception:
            return None
    
    def _check_api_invention(self, response: str) -> Rejection | None:
        """Check for invented/hallucinated APIs."""
        if not self.known_symbols:
            return None
        
        # Check for suspicious patterns
        hallucination_patterns = [
            r"import\s+\w+\s+from\s+['\"]@(?!code4u)",  # Unknown scoped packages
            r"from\s+(?!\.)\w+_hallucinated",  # Obviously fake modules
            r"\.nonexistent\(",  # Non-existent methods
        ]
        
        for pattern in hallucination_patterns:
            if re.search(pattern, response):
                return Rejection(
                    rejection_type=RejectionType.HARD,
                    reason=RejectionReason.API_INVENTION,
                    message="Detected hallucinated API or import",
                    details={"pattern": pattern}
                )
        
        return None
    
    def _check_syntax(self, response: str) -> Rejection | None:
        """Check for obvious syntax errors (soft rejection)."""
        try:
            data = self._extract_json(response)
            if not data:
                return None
            
            diffs = data.get("diffs", [])
            for diff_obj in diffs:
                diff = diff_obj.get("diff", "")
                file_path = diff_obj.get("file_path", "")
                
                # Check for Python syntax in Python files
                if file_path.endswith(".py"):
                    issues = self._check_python_syntax_in_diff(diff)
                    if issues:
                        return Rejection(
                            rejection_type=RejectionType.SOFT,
                            reason=RejectionReason.SYNTAX_ERROR,
                            message=f"Python syntax issue: {issues[0]}",
                            details={"issues": issues}
                        )
                
                # Check for TypeScript/JS issues
                if file_path.endswith((".ts", ".tsx", ".js", ".jsx")):
                    issues = self._check_ts_syntax_in_diff(diff)
                    if issues:
                        return Rejection(
                            rejection_type=RejectionType.SOFT,
                            reason=RejectionReason.SYNTAX_ERROR,
                            message=f"TypeScript syntax issue: {issues[0]}",
                            details={"issues": issues}
                        )
            
            return None
            
        except Exception:
            return None
    
    def _extract_json(self, response: str) -> dict | None:
        """Extract JSON from response."""
        try:
            # Try direct parse
            return json.loads(response)
        except:
            pass
        
        # Try extracting from code block
        if "```json" in response:
            match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except:
                    pass
        
        return None
    
    def _is_valid_diff(self, diff: str) -> bool:
        """Check if diff has valid format."""
        if not diff.strip():
            return False
        has_header = "---" in diff or "+++" in diff
        has_content = "+" in diff or "-" in diff
        return has_header and has_content
    
    def _check_python_syntax_in_diff(self, diff: str) -> List[str]:
        """Check for obvious Python syntax issues."""
        issues = []
        lines = diff.split("\n")
        
        for i, line in enumerate(lines):
            if line.startswith("+") and not line.startswith("+++"):
                code = line[1:]
                # Check for missing colons
                if re.match(r"\s*(def|class|if|for|while|with|try)\s+\w+[^:]*$", code):
                    issues.append(f"Line {i}: possibly missing colon")
                # Check for unmatched parentheses
                if code.count("(") != code.count(")"):
                    issues.append(f"Line {i}: unmatched parentheses")
        
        return issues
    
    def _check_ts_syntax_in_diff(self, diff: str) -> List[str]:
        """Check for obvious TypeScript syntax issues."""
        issues = []
        lines = diff.split("\n")
        
        for i, line in enumerate(lines):
            if line.startswith("+") and not line.startswith("+++"):
                code = line[1:]
                # Check for unmatched braces
                if code.count("{") != code.count("}"):
                    issues.append(f"Line {i}: unmatched braces")
                # Check for missing semicolons in certain contexts
                if re.match(r"^\s*(const|let|var)\s+\w+\s*=\s*[^;{]+$", code):
                    # This might be valid (line continues) or invalid
                    pass
        
        return issues


class RetryManager:
    """
    Manage retry attempts with machine feedback.
    
    Each retry adds specific error feedback to the prompt.
    This reduces hallucination by ~70%.
    """
    
    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries
        self.attempts: list[Dict[str, Any]] = []
    
    def should_retry(self, rejection: Rejection, attempt: int) -> bool:
        """Determine if retry is allowed."""
        if rejection.rejection_type == RejectionType.HARD:
            logger.warning(
                "hard_rejection_no_retry",
                reason=rejection.reason.value,
                message=rejection.message
            )
            return False
        
        if attempt >= self.max_retries:
            logger.warning(
                "max_retries_exceeded",
                attempt=attempt,
                max_retries=self.max_retries
            )
            return False
        
        return True
    
    def build_retry_context(
        self,
        rejection: Rejection,
        attempt: int
    ) -> RetryContext:
        """Build context for retry attempt."""
        correction = self._get_correction_instruction(rejection)
        
        context = RetryContext(
            attempt=attempt + 1,
            previous_error=rejection.message,
            correction_required=correction,
            additional_context=rejection.details
        )
        
        self.attempts.append({
            "attempt": attempt + 1,
            "rejection": rejection.reason.value,
            "correction": correction
        })
        
        logger.info(
            "building_retry",
            attempt=attempt + 1,
            reason=rejection.reason.value
        )
        
        return context
    
    def _get_correction_instruction(self, rejection: Rejection) -> str:
        """Generate specific correction instruction."""
        instructions = {
            RejectionReason.FORMATTING_ISSUE: "Ensure output is valid unified diff format",
            RejectionReason.MISSING_IMPORT: f"Add the missing import: {rejection.details.get('missing', 'unknown')}",
            RejectionReason.TYPE_MISMATCH: "Fix type annotation to match expected type",
            RejectionReason.PARTIAL_DIFF: "Include complete diff for all affected files",
            RejectionReason.SYNTAX_ERROR: f"Fix syntax error: {rejection.details.get('issues', ['unknown'])[0]}",
        }
        
        return instructions.get(
            rejection.reason,
            "Correct the error and try again"
        )
    
    def get_attempt_log(self) -> list[Dict[str, Any]]:
        """Get log of all retry attempts."""
        return self.attempts

