from __future__ import annotations
"""Unified diff validation for code4u.ai."""
from dataclasses import dataclass, field
from enum import Enum
import re
import structlog
from typing import List, Optional, Tuple

logger = structlog.get_logger("validation.diff")


class ValidationLevel(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """A validation issue."""
    level: ValidationLevel
    message: str
    line: Optional[int] = None
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of diff validation."""
    valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    
    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.level == ValidationLevel.ERROR]
    
    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.level == ValidationLevel.WARNING]


class DiffValidator:
    """
    Validate unified diff format and content.
    
    Checks:
    - Valid unified diff structure
    - Consistent line numbers
    - Non-empty changes
    - File path format
    """
    
    def validate(self, diff: str) -> ValidationResult:
        """Validate a unified diff."""
        issues: list[ValidationIssue] = []
        
        if not diff or not diff.strip():
            return ValidationResult(
                valid=False,
                issues=[ValidationIssue(
                    level=ValidationLevel.ERROR,
                    message="Empty diff"
                )]
            )
        
        lines = diff.strip().split("\n")
        
        # Check for rejection marker
        if "INSUFFICIENT_CONTEXT" in diff:
            return ValidationResult(
                valid=False,
                issues=[ValidationIssue(
                    level=ValidationLevel.ERROR,
                    message="LLM rejected due to insufficient context"
                )]
            )
        
        # Check diff structure
        issues.extend(self._validate_structure(lines))
        
        # Check hunk format
        issues.extend(self._validate_hunks(lines))
        
        # Check for suspicious patterns
        issues.extend(self._check_suspicious_patterns(lines))
        
        valid = not any(i.level == ValidationLevel.ERROR for i in issues)
        
        logger.info(
            "diff_validated",
            valid=valid,
            errors=len([i for i in issues if i.level == ValidationLevel.ERROR]),
            warnings=len([i for i in issues if i.level == ValidationLevel.WARNING])
        )
        
        return ValidationResult(valid=valid, issues=issues)
    
    def _validate_structure(self, lines: List[str]) -> list[ValidationIssue]:
        """Validate basic diff structure."""
        issues = []
        
        has_minus_header = False
        has_plus_header = False
        has_hunk = False
        
        for i, line in enumerate(lines):
            if line.startswith("---"):
                has_minus_header = True
            elif line.startswith("+++"):
                has_plus_header = True
            elif line.startswith("@@"):
                has_hunk = True
        
        if not has_minus_header:
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                message="Missing '---' header",
                suggestion="Diff must start with '--- a/path/to/file'"
            ))
        
        if not has_plus_header:
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                message="Missing '+++' header",
                suggestion="Diff must have '+++ b/path/to/file'"
            ))
        
        if not has_hunk:
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                message="No diff hunks found",
                suggestion="Diff must have at least one '@@ ... @@' hunk"
            ))
        
        return issues
    
    def _validate_hunks(self, lines: List[str]) -> list[ValidationIssue]:
        """Validate hunk headers and content."""
        issues = []
        hunk_pattern = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
        
        in_hunk = False
        expected_minus = 0
        expected_plus = 0
        actual_minus = 0
        actual_plus = 0
        
        for i, line in enumerate(lines):
            match = hunk_pattern.match(line)
            if match:
                # Check previous hunk
                if in_hunk:
                    if actual_minus != expected_minus:
                        issues.append(ValidationIssue(
                            level=ValidationLevel.WARNING,
                            message=f"Hunk line count mismatch: expected {expected_minus} deletions, got {actual_minus}",
                            line=i
                        ))
                
                # Start new hunk
                in_hunk = True
                expected_minus = int(match.group(2) or 1)
                expected_plus = int(match.group(4) or 1)
                actual_minus = 0
                actual_plus = 0
                
            elif in_hunk:
                if line.startswith("-"):
                    actual_minus += 1
                elif line.startswith("+"):
                    actual_plus += 1
                elif line.startswith(" "):
                    actual_minus += 1
                    actual_plus += 1
        
        return issues
    
    def _check_suspicious_patterns(self, lines: List[str]) -> list[ValidationIssue]:
        """Check for suspicious patterns that indicate hallucination."""
        issues = []
        
        suspicious_patterns = [
            (r"import\s+\w+\s+from\s+['\"]@nonexistent", "Possible hallucinated import"),
            (r"from\s+nonexistent\s+import", "Possible hallucinated Python import"),
            (r"TODO:\s*implement", "Contains TODO marker"),
            (r"# ?\.\.\.", "Contains placeholder comment"),
            (r"pass\s*#\s*implement", "Contains unimplemented placeholder"),
        ]
        
        for i, line in enumerate(lines):
            if line.startswith("+"):  # Only check additions
                for pattern, message in suspicious_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        issues.append(ValidationIssue(
                            level=ValidationLevel.WARNING,
                            message=message,
                            line=i + 1,
                            suggestion="Review this line for hallucinated content"
                        ))
        
        return issues
    
    def apply_diff(self, original: str, diff: str) -> Tuple[str, bool]:
        """
        Apply a validated diff to original content.
        
        Returns (new_content, success).
        """
        validation = self.validate(diff)
        if not validation.valid:
            return original, False
        
        try:
            lines = original.split("\n")
            diff_lines = diff.strip().split("\n")
            
            # Simple application - production would use proper patch library
            result_lines = []
            original_idx = 0
            in_hunk = False
            
            hunk_pattern = re.compile(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
            
            for diff_line in diff_lines:
                if diff_line.startswith("---") or diff_line.startswith("+++"):
                    continue
                    
                match = hunk_pattern.match(diff_line)
                if match:
                    start_line = int(match.group(1)) - 1
                    # Copy lines before hunk
                    while original_idx < start_line:
                        result_lines.append(lines[original_idx])
                        original_idx += 1
                    in_hunk = True
                    continue
                
                if in_hunk:
                    if diff_line.startswith("+"):
                        result_lines.append(diff_line[1:])
                    elif diff_line.startswith("-"):
                        original_idx += 1
                    elif diff_line.startswith(" "):
                        result_lines.append(diff_line[1:])
                        original_idx += 1
            
            # Copy remaining lines
            while original_idx < len(lines):
                result_lines.append(lines[original_idx])
                original_idx += 1
            
            return "\n".join(result_lines), True
            
        except Exception as e:
            logger.error("diff_apply_failed", error=str(e))
            return original, False

