"""Diagnoser — Root Cause Analysis via DependencyMap.

Given a ``ParsedError``, the ``Diagnoser`` uses the code knowledge
graph to:

  1. Read the failing file and extract the context window around the
     error line.
  2. Identify symbols referenced on the failing line and look up their
     definitions in the ``DependencyMap``.
  3. Classify the error type and generate targeted ``RepairSuggestion``
     entries (e.g., "add missing import", "rename symbol").
  4. For import/attribute errors, trace through the dependency graph to
     find the correct source module.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import structlog

from code4u.agents.healing.parser import ParsedError, ErrorFrame, Language

logger = structlog.get_logger("diagnoser")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ContextWindow:
    """Source code around the error location."""
    file_path: str
    error_line: int
    lines: Dict[int, str] = field(default_factory=dict)
    symbols_on_line: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filePath": self.file_path,
            "errorLine": self.error_line,
            "lines": {str(k): v for k, v in self.lines.items()},
            "symbolsOnLine": self.symbols_on_line,
        }


@dataclass
class SymbolTrace:
    """Where a symbol is defined and who uses it."""
    symbol_name: str
    defined_in: str = ""
    defined_at_line: int = 0
    kind: str = ""
    used_by: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbolName": self.symbol_name,
            "definedIn": self.defined_in,
            "definedAtLine": self.defined_at_line,
            "kind": self.kind,
            "usedBy": self.used_by,
        }


@dataclass
class RepairSuggestion:
    """A proposed fix for a diagnosed error."""
    file_path: str
    description: str
    action: str  # "add_import", "rename_symbol", "fix_attribute", "add_definition", "generic"
    old_text: str = ""
    new_text: str = ""
    line_number: int = 0
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filePath": self.file_path,
            "description": self.description,
            "action": self.action,
            "oldText": self.old_text,
            "newText": self.new_text,
            "lineNumber": self.line_number,
            "confidence": round(self.confidence, 2),
        }


@dataclass
class Diagnosis:
    """Complete diagnosis of an error."""
    error: ParsedError
    context: Optional[ContextWindow] = None
    symbol_traces: List[SymbolTrace] = field(default_factory=list)
    suggestions: List[RepairSuggestion] = field(default_factory=list)
    root_cause: str = ""
    severity: str = "error"

    @property
    def has_fix(self) -> bool:
        return len(self.suggestions) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": self.error.to_dict(),
            "context": self.context.to_dict() if self.context else None,
            "symbolTraces": [s.to_dict() for s in self.symbol_traces],
            "suggestions": [s.to_dict() for s in self.suggestions],
            "rootCause": self.root_cause,
            "severity": self.severity,
            "hasFix": self.has_fix,
        }


# ---------------------------------------------------------------------------
# Diagnoser
# ---------------------------------------------------------------------------

class Diagnoser:
    """Root cause analyzer that uses the DependencyMap for context.

    Usage::

        diagnoser = Diagnoser(dep_map)
        diagnosis = diagnoser.diagnose(parsed_error)
        for suggestion in diagnosis.suggestions:
            print(suggestion.description)
    """

    CONTEXT_RADIUS = 5  # lines above and below the error

    def __init__(self, dep_map: Any) -> None:
        self._dep_map = dep_map

    def diagnose(self, error: ParsedError) -> Diagnosis:
        """Perform full root cause analysis on a parsed error."""
        diagnosis = Diagnosis(error=error)

        frame = error.failing_frame
        if not frame:
            diagnosis.root_cause = "No stack frame available for analysis"
            return diagnosis

        # Step 1: Build context window
        diagnosis.context = self._build_context(frame)

        # Step 2: Identify symbols on the failing line
        if diagnosis.context:
            for sym_name in diagnosis.context.symbols_on_line:
                trace = self._trace_symbol(sym_name)
                if trace:
                    diagnosis.symbol_traces.append(trace)

        # Step 3: Classify error and generate repair suggestions
        self._classify_and_suggest(diagnosis)

        logger.info(
            "diagnosis_complete",
            error_type=error.error_type,
            file=frame.file_path,
            line=frame.line_number,
            suggestions=len(diagnosis.suggestions),
        )

        return diagnosis

    def diagnose_all(self, errors: List[ParsedError]) -> List[Diagnosis]:
        """Diagnose a batch of errors."""
        return [self.diagnose(e) for e in errors]

    # -- Context window ------------------------------------------------------

    def _build_context(self, frame: ErrorFrame) -> Optional[ContextWindow]:
        """Read source lines around the error and identify symbols."""
        try:
            content = Path(frame.file_path).read_text(encoding="utf-8")
        except Exception:
            return None

        lines = content.splitlines()
        start = max(0, frame.line_number - self.CONTEXT_RADIUS - 1)
        end = min(len(lines), frame.line_number + self.CONTEXT_RADIUS)

        line_map: Dict[int, str] = {}
        for i in range(start, end):
            line_map[i + 1] = lines[i]

        # Extract identifiers from the failing line
        symbols: List[str] = []
        if frame.line_number <= len(lines):
            failing = lines[frame.line_number - 1]
            symbols = self._extract_identifiers(failing)

        return ContextWindow(
            file_path=frame.file_path,
            error_line=frame.line_number,
            lines=line_map,
            symbols_on_line=symbols,
        )

    def _extract_identifiers(self, line: str) -> List[str]:
        """Extract Python/JS identifiers from a source line."""
        # Remove string literals and comments
        cleaned = re.sub(r'["\'].*?["\']', '', line)
        cleaned = re.sub(r'#.*$', '', cleaned)
        cleaned = re.sub(r'//.*$', '', cleaned)

        idents = re.findall(r'\b([a-zA-Z_]\w*)\b', cleaned)
        # Filter out keywords and builtins
        keywords = {
            "if", "else", "elif", "for", "while", "def", "class", "import",
            "from", "return", "yield", "try", "except", "finally", "with",
            "as", "in", "is", "not", "and", "or", "True", "False", "None",
            "pass", "break", "continue", "raise", "assert", "lambda",
            "async", "await", "print", "len", "range", "str", "int",
            "float", "list", "dict", "set", "tuple", "self", "super",
            "type", "isinstance", "hasattr", "getattr", "setattr",
            "const", "let", "var", "function", "new", "this", "typeof",
            "undefined", "null", "require", "export", "default",
        }
        return [i for i in idents if i not in keywords]

    # -- Symbol tracing ------------------------------------------------------

    def _trace_symbol(self, symbol_name: str) -> Optional[SymbolTrace]:
        """Look up a symbol in the DependencyMap."""
        defs = self._dep_map.get_symbol_defs(symbol_name)
        if not defs:
            return SymbolTrace(symbol_name=symbol_name)

        primary = defs[0]
        dependents = self._dep_map.get_dependents(symbol_name)

        return SymbolTrace(
            symbol_name=symbol_name,
            defined_in=primary.file_path,
            defined_at_line=primary.start_line,
            kind=primary.kind,
            used_by=dependents[:10],
        )

    # -- Classification and repair -------------------------------------------

    def _classify_and_suggest(self, diagnosis: Diagnosis) -> None:
        """Classify the error type and generate repair suggestions."""
        err = diagnosis.error
        err_type = err.error_type.lower()

        if "importerror" in err_type or "modulenotfounderror" in err_type:
            self._suggest_import_fix(diagnosis)
        elif "nameerror" in err_type:
            self._suggest_name_fix(diagnosis)
        elif "attributeerror" in err_type:
            self._suggest_attribute_fix(diagnosis)
        elif "typeerror" in err_type:
            self._suggest_type_fix(diagnosis)
        elif "syntaxerror" in err_type:
            self._suggest_syntax_fix(diagnosis)
        elif "assertionerror" in err_type or "testfailure" in err_type:
            self._suggest_assertion_fix(diagnosis)
        elif "referenceerror" in err_type:
            self._suggest_name_fix(diagnosis)
        else:
            self._suggest_generic_fix(diagnosis)

    def _suggest_import_fix(self, diagnosis: Diagnosis) -> None:
        """Handle ImportError / ModuleNotFoundError."""
        msg = diagnosis.error.message
        frame = diagnosis.error.failing_frame

        # Extract the missing module/symbol name
        m = re.search(r"cannot import name '(\w+)'", msg)
        if m:
            missing = m.group(1)
            diagnosis.root_cause = f"Symbol '{missing}' cannot be imported — it may have been moved or renamed"

            # Search for the symbol in the dep map
            defs = self._dep_map.get_symbol_defs(missing)
            if defs:
                correct_file = defs[0].file_path
                correct_module = Path(correct_file).stem
                diagnosis.suggestions.append(RepairSuggestion(
                    file_path=frame.file_path if frame else "",
                    description=f"Update import to use '{correct_module}' where '{missing}' is now defined",
                    action="add_import",
                    new_text=f"from {correct_module} import {missing}",
                    confidence=0.9,
                ))
            return

        m = re.search(r"No module named '(\S+)'", msg)
        if m:
            missing_mod = m.group(1)
            diagnosis.root_cause = f"Module '{missing_mod}' not found — may need to be installed or path fixed"
            diagnosis.suggestions.append(RepairSuggestion(
                file_path=frame.file_path if frame else "",
                description=f"Module '{missing_mod}' is missing. Install it or check the import path.",
                action="add_import",
                confidence=0.5,
            ))

    def _suggest_name_fix(self, diagnosis: Diagnosis) -> None:
        """Handle NameError / ReferenceError — undefined variable."""
        msg = diagnosis.error.message
        frame = diagnosis.error.failing_frame

        m = re.search(r"name '(\w+)' is not defined", msg)
        if not m:
            m = re.search(r"(\w+) is not defined", msg)
        if not m:
            diagnosis.root_cause = f"Undefined name: {msg}"
            return

        missing = m.group(1)
        diagnosis.root_cause = f"Name '{missing}' is not defined in scope"

        # Check if the symbol exists elsewhere in the codebase
        defs = self._dep_map.get_symbol_defs(missing)
        if defs:
            source_file = defs[0].file_path
            source_module = Path(source_file).stem
            diagnosis.suggestions.append(RepairSuggestion(
                file_path=frame.file_path if frame else "",
                description=f"Add missing import: '{missing}' is defined in '{source_module}'",
                action="add_import",
                new_text=f"from {source_module} import {missing}",
                line_number=1,
                confidence=0.85,
            ))
        else:
            # Symbol doesn't exist — might be a typo
            self._suggest_typo_fix(diagnosis, missing)

    def _suggest_attribute_fix(self, diagnosis: Diagnosis) -> None:
        """Handle AttributeError — wrong attribute access."""
        msg = diagnosis.error.message
        frame = diagnosis.error.failing_frame

        m = re.search(r"'(\w+)' object has no attribute '(\w+)'", msg)
        if m:
            obj_type = m.group(1)
            attr = m.group(2)
            diagnosis.root_cause = f"'{obj_type}' does not have attribute '{attr}'"

            # Look for the attribute in the dep map
            defs = self._dep_map.get_symbol_defs(attr)
            if defs:
                diagnosis.suggestions.append(RepairSuggestion(
                    file_path=frame.file_path if frame else "",
                    description=f"'{attr}' exists in '{Path(defs[0].file_path).name}' — object type mismatch or missing initialization",
                    action="fix_attribute",
                    confidence=0.6,
                ))
        else:
            diagnosis.root_cause = f"Attribute error: {msg}"

    def _suggest_type_fix(self, diagnosis: Diagnosis) -> None:
        """Handle TypeError — wrong argument count, wrong type, etc."""
        msg = diagnosis.error.message
        diagnosis.root_cause = f"Type error: {msg}"

        m = re.search(r"(\w+)\(\) takes (\d+) positional arguments? but (\d+) (?:was|were) given", msg)
        if m:
            func_name = m.group(1)
            expected = m.group(2)
            got = m.group(3)
            diagnosis.suggestions.append(RepairSuggestion(
                file_path=diagnosis.error.failing_file,
                description=f"'{func_name}()' expects {expected} args but got {got} — check call site",
                action="generic",
                confidence=0.7,
            ))

    def _suggest_syntax_fix(self, diagnosis: Diagnosis) -> None:
        """Handle SyntaxError."""
        diagnosis.root_cause = f"Syntax error: {diagnosis.error.message}"
        diagnosis.severity = "critical"
        if diagnosis.error.failing_frame:
            diagnosis.suggestions.append(RepairSuggestion(
                file_path=diagnosis.error.failing_file,
                description=f"Fix syntax error at line {diagnosis.error.failing_line}",
                action="generic",
                line_number=diagnosis.error.failing_line,
                confidence=0.5,
            ))

    def _suggest_assertion_fix(self, diagnosis: Diagnosis) -> None:
        """Handle AssertionError / test failures."""
        diagnosis.root_cause = f"Test assertion failed: {diagnosis.error.message}"
        diagnosis.severity = "warning"

        if diagnosis.context:
            for sym in diagnosis.context.symbols_on_line:
                trace = self._trace_symbol(sym)
                if trace and trace.defined_in:
                    diagnosis.suggestions.append(RepairSuggestion(
                        file_path=trace.defined_in,
                        description=f"Check '{sym}' (defined at line {trace.defined_at_line}) — test expects different behavior",
                        action="generic",
                        line_number=trace.defined_at_line,
                        confidence=0.4,
                    ))

    def _suggest_generic_fix(self, diagnosis: Diagnosis) -> None:
        """Fallback for unrecognized error types."""
        diagnosis.root_cause = f"{diagnosis.error.error_type}: {diagnosis.error.message}"

    def _suggest_typo_fix(self, diagnosis: Diagnosis, missing: str) -> None:
        """Suggest similar symbol names (typo correction)."""
        all_symbols = set()
        for fp in self._dep_map.all_files:
            for sd in self._dep_map.get_file_symbols(fp):
                all_symbols.add(sd.name)

        # Simple edit-distance-1 matching
        candidates = []
        for sym in all_symbols:
            if self._is_similar(missing, sym):
                candidates.append(sym)

        if candidates:
            best = candidates[0]
            defs = self._dep_map.get_symbol_defs(best)
            source = Path(defs[0].file_path).stem if defs else "?"
            diagnosis.suggestions.append(RepairSuggestion(
                file_path=diagnosis.error.failing_file,
                description=f"Did you mean '{best}'? (defined in '{source}')",
                action="rename_symbol",
                old_text=missing,
                new_text=best,
                confidence=0.7,
            ))

    @staticmethod
    def _is_similar(a: str, b: str) -> bool:
        """Check if two names are within edit distance 1."""
        if abs(len(a) - len(b)) > 1:
            return False
        if a.lower() == b.lower():
            return True
        diffs = sum(1 for x, y in zip(a, b) if x != y)
        if len(a) == len(b):
            return diffs <= 1
        # Insertion/deletion check
        longer, shorter = (a, b) if len(a) > len(b) else (b, a)
        j = 0
        mismatches = 0
        for i in range(len(longer)):
            if j < len(shorter) and longer[i] == shorter[j]:
                j += 1
            else:
                mismatches += 1
        return mismatches <= 1
