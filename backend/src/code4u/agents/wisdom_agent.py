"""Wisdom Agent — Collective Intelligence Query Engine.

During the Gauntlet validation loop, this agent queries the central
knowledge store: "Has anyone in this company fixed a similar problem
before?" If a match is found, it provides the historical fix as a
suggestion.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger("wisdom_agent")


@dataclass
class WisdomSuggestion:
    """A suggested fix from collective intelligence."""

    file_path: str
    issue_description: str
    suggested_fix: str
    confidence: float
    source_nugget_id: str
    source_project: str
    pattern_type: str
    language: str

    def to_dict(self) -> Dict[str, Any]:
        """Return dict with camelCase keys."""
        return {
            "filePath": self.file_path,
            "issueDescription": self.issue_description,
            "suggestedFix": self.suggested_fix,
            "confidence": self.confidence,
            "sourceNuggetId": self.source_nugget_id,
            "sourceProject": self.source_project,
            "patternType": self.pattern_type,
            "language": self.language,
        }


@dataclass
class DuplicateCandidate:
    """A function that semantically duplicates one from another project."""

    function_name: str
    file_path: str
    project: str
    similarity: float
    original_function: str
    original_project: str
    original_file: str
    recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        """Return dict with camelCase keys."""
        return {
            "functionName": self.function_name,
            "filePath": self.file_path,
            "project": self.project,
            "similarity": self.similarity,
            "originalFunction": self.original_function,
            "originalProject": self.original_project,
            "originalFile": self.original_file,
            "recommendation": self.recommendation,
        }


class WisdomAgent:
    """Queries collective intelligence during validation."""

    def __init__(self) -> None:
        self._suggestion_cache: List[WisdomSuggestion] = []

    def analyze_code_for_suggestions(
        self,
        code_map: Dict[str, str],
        failures: Optional[List[Dict[str, Any]]] = None,
    ) -> List[WisdomSuggestion]:
        """Query the wisdom store for suggestions based on code patterns."""
        from code4u.knowledge.pattern_extractor import get_pattern_extractor
        extractor = get_pattern_extractor()
        suggestions: List[WisdomSuggestion] = []

        for filepath, content in code_map.items():
            # Search for patterns matching current code issues
            issues = self._detect_known_anti_patterns(filepath, content)
            for issue in issues:
                nuggets = extractor.search_nuggets(
                    query=issue["query"],
                    language=self._detect_language(filepath),
                    limit=3,
                )
                for nugget in nuggets:
                    if nugget.confidence > 0.2:
                        suggestions.append(WisdomSuggestion(
                            file_path=filepath,
                            issue_description=issue["description"],
                            suggested_fix=nugget.after_snippet[:500],
                            confidence=nugget.confidence,
                            source_nugget_id=nugget.nugget_id,
                            source_project=nugget.source_project,
                            pattern_type=nugget.pattern_type,
                            language=nugget.language,
                        ))

        # Also check failures if provided
        if failures:
            for failure in failures:
                query = failure.get("error", "") + " " + failure.get("test_name", "")
                nuggets = extractor.search_nuggets(query=query, limit=2)
                for nugget in nuggets:
                    if nugget.confidence > 0.3:
                        suggestions.append(WisdomSuggestion(
                            file_path=failure.get("file_path", ""),
                            issue_description=failure.get("error", ""),
                            suggested_fix=nugget.after_snippet[:500],
                            confidence=nugget.confidence,
                            source_nugget_id=nugget.nugget_id,
                            source_project=nugget.source_project,
                            pattern_type=nugget.pattern_type,
                            language=nugget.language,
                        ))

        self._suggestion_cache = suggestions
        return suggestions

    def _detect_known_anti_patterns(self, filepath: str, content: str) -> List[Dict[str, str]]:
        """Detect anti-patterns that might have been fixed before in other projects."""
        patterns = []
        # Build a list of queries based on detected anti-patterns
        anti_patterns = [
            (r'eval\s*\(', "eval usage", "eval injection security fix"),
            (r'f["\'].*SELECT.*\{', "SQL injection pattern", "sql injection parameterized query fix"),
            (r'innerHTML\s*=', "innerHTML XSS risk", "innerHTML XSS sanitization fix"),
            (r'password\s*=\s*["\']', "hardcoded password", "hardcoded credential removal"),
            (r'except\s*:', "bare except clause", "error handling improvement"),
            (r'# TODO', "TODO comment", "incomplete implementation"),
            (r'time\.sleep\s*\(', "blocking sleep", "async sleep conversion"),
            (r'print\s*\(', "print statement in production", "logging framework migration"),
            (r'\.readlines\s*\(\s*\)', "memory-heavy file read", "streaming file read optimization"),
        ]
        for pattern, desc, query in anti_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                patterns.append({"description": desc, "query": query})
        return patterns[:5]

    def _detect_language(self, filepath: str) -> str:
        ext = filepath.rsplit(".", 1)[-1].lower() if "." in filepath else ""
        lang_map = {
            "py": "python", "js": "javascript", "ts": "typescript",
            "tsx": "typescript", "jsx": "javascript", "go": "go",
            "rs": "rust", "java": "java", "rb": "ruby", "php": "php",
        }
        return lang_map.get(ext, "unknown")

    def find_semantic_duplicates(
        self,
        code_map: Dict[str, str],
        project_name: str = "",
    ) -> List[DuplicateCandidate]:
        """Find functions that semantically duplicate existing ones in other projects."""
        from code4u.knowledge.pattern_extractor import get_pattern_extractor
        extractor = get_pattern_extractor()
        duplicates: List[DuplicateCandidate] = []

        current_project_hash = hashlib.sha256(project_name.encode()).hexdigest()[:12] if project_name else ""

        for filepath, content in code_map.items():
            functions = self._extract_functions(filepath, content)
            for func_name, func_body in functions:
                # Search wisdom store for similar function bodies
                nuggets = extractor.search_nuggets(
                    query=func_body[:200],
                    language=self._detect_language(filepath),
                    limit=3,
                )
                for nugget in nuggets:
                    if nugget.confidence > 0.4 and nugget.source_project != current_project_hash:
                        duplicates.append(DuplicateCandidate(
                            function_name=func_name,
                            file_path=filepath,
                            project=project_name,
                            similarity=round(nugget.confidence, 2),
                            original_function=nugget.description,
                            original_project=nugget.source_project,
                            original_file="(anonymized)",
                            recommendation=f"Consider importing from shared library instead of reimplementing. Pattern: {nugget.pattern_type}",
                        ))

        duplicates.sort(key=lambda d: d.similarity, reverse=True)
        return duplicates

    def _extract_functions(self, filepath: str, content: str) -> List[tuple]:
        """Extract function names and bodies from code."""
        import ast as ast_mod
        functions = []
        if filepath.endswith(".py"):
            try:
                tree = ast_mod.parse(content)
                lines = content.splitlines()
                for node in ast_mod.walk(tree):
                    if isinstance(node, (ast_mod.FunctionDef, ast_mod.AsyncFunctionDef)):
                        end_line = getattr(node, 'end_lineno', node.lineno + 10)
                        body = "\n".join(lines[node.lineno - 1:end_line])
                        functions.append((node.name, body))
            except SyntaxError:
                pass
        else:
            # Simple regex for JS/TS
            for m in re.finditer(r'(?:function\s+(\w+)|const\s+(\w+)\s*=.*=>)', content):
                name = m.group(1) or m.group(2) or "anonymous"
                start = m.start()
                end = min(start + 500, len(content))
                functions.append((name, content[start:end]))
        return functions[:20]

    def get_suggestions(self) -> List[WisdomSuggestion]:
        return list(self._suggestion_cache)

    def generate_report(self, suggestions: List[WisdomSuggestion]) -> str:
        """Generate Markdown wisdom report."""
        lines = [
            "# Collective Intelligence Report",
            "",
            f"**Suggestions Found:** {len(suggestions)}",
            "",
        ]
        if not suggestions:
            lines.append("No relevant historical fixes found for this code.")
        else:
            lines.append("## Suggested Fixes from Corporate Knowledge")
            lines.append("")
            for s in suggestions:
                lines.append(f"### {s.file_path}")
                lines.append(f"- **Issue:** {s.issue_description}")
                lines.append(f"- **Confidence:** {s.confidence*100:.0f}%")
                lines.append(f"- **Source:** Project `{s.source_project}` ({s.pattern_type})")
                lines.append(f"- **Suggested Fix:**")
                lines.append(f"```")
                lines.append(s.suggested_fix[:300])
                lines.append(f"```")
                lines.append("")
        return "\n".join(lines)
