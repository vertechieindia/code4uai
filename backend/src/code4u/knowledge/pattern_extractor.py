"""Cross-Project Pattern Extractor — Wisdom Nugget Storage.

When the HealAgent fixes a bug, this module extracts the 'Before' and
'After' snippets, anonymizes them (removes IDs, keys, PII), and stores
them in a central vector store as 'Wisdom Nuggets'.

These nuggets can be queried across projects to share collective
knowledge about how specific patterns of bugs were fixed.
"""

from __future__ import annotations

import hashlib
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger("pattern_extractor")


@dataclass
class WisdomNugget:
    """A stored fix pattern from collective intelligence."""

    nugget_id: str
    pattern_type: str
    language: str
    before_snippet: str
    after_snippet: str
    description: str
    tags: List[str]
    source_project: str
    created_at: float
    usage_count: int = 0
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Return dict with camelCase keys."""
        return {
            "nuggetId": self.nugget_id,
            "patternType": self.pattern_type,
            "language": self.language,
            "beforeSnippet": self.before_snippet,
            "afterSnippet": self.after_snippet,
            "description": self.description,
            "tags": self.tags,
            "sourceProject": self.source_project,
            "createdAt": self.created_at,
            "usageCount": self.usage_count,
            "confidence": self.confidence,
        }


class PatternExtractor:
    """Extracts, anonymizes, and stores fix patterns as Wisdom Nuggets."""

    ANONYMIZE_PATTERNS = [
        (r'AKIA[0-9A-Z]{16}', 'AWS_KEY_REDACTED'),
        (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', 'EMAIL_REDACTED'),
        (r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', 'IP_REDACTED'),
        (r'https?://[^\s"\']+', 'URL_REDACTED'),
        (r'["\'][a-zA-Z0-9_-]{32,}["\']', '"TOKEN_REDACTED"'),
        (r'password\s*=\s*["\'][^"\']+["\']', 'password="REDACTED"'),
        (r'api_key\s*=\s*["\'][^"\']+["\']', 'api_key="REDACTED"'),
        (r'secret\s*=\s*["\'][^"\']+["\']', 'secret="REDACTED"'),
        (r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', 'UUID_REDACTED'),
    ]

    def __init__(self) -> None:
        self._nuggets: Dict[str, WisdomNugget] = {}
        self._embedder = None  # Lazy init

    def _get_embedder(self):
        if self._embedder is None:
            from code4u.ai_engine.vector_store import TFIDFEmbedder
            self._embedder = TFIDFEmbedder()
        return self._embedder

    def anonymize(self, text: str) -> str:
        """Remove sensitive data from code snippets."""
        result = text
        for pattern, replacement in self.ANONYMIZE_PATTERNS:
            result = re.sub(pattern, replacement, result)
        return result

    def extract_pattern(
        self,
        before: str,
        after: str,
        language: str = "python",
        pattern_type: str = "bug_fix",
        description: str = "",
        tags: Optional[List[str]] = None,
        source_project: str = "",
    ) -> WisdomNugget:
        """Extract and store a fix pattern as a Wisdom Nugget."""
        anon_before = self.anonymize(before)
        anon_after = self.anonymize(after)

        project_hash = hashlib.sha256(source_project.encode()).hexdigest()[:12] if source_project else "unknown"

        if not description:
            description = self._auto_describe(anon_before, anon_after, language)

        nugget = WisdomNugget(
            nugget_id=str(uuid.uuid4()),
            pattern_type=pattern_type,
            language=language,
            before_snippet=anon_before[:2000],
            after_snippet=anon_after[:2000],
            description=description,
            tags=tags or self._auto_tag(anon_before, anon_after),
            source_project=project_hash,
            created_at=time.time(),
            confidence=self._compute_confidence(anon_before, anon_after),
        )

        self._nuggets[nugget.nugget_id] = nugget
        logger.info("wisdom_nugget_stored", nugget_id=nugget.nugget_id, pattern_type=pattern_type, language=language)
        return nugget

    def _auto_describe(self, before: str, after: str, language: str) -> str:
        """Generate automatic description of the fix."""
        descriptions = []
        # Detect common fix patterns
        if "eval(" in before and "eval(" not in after:
            descriptions.append("Removed dangerous eval() usage")
        if "SELECT" in before and "parameterized" in after.lower():
            descriptions.append("Fixed SQL injection via parameterized queries")
        if "innerHTML" in before and ("textContent" in after or "sanitize" in after.lower()):
            descriptions.append("Fixed XSS by replacing innerHTML with safe alternative")
        if "password" in before.lower() and ("hash" in after.lower() or "bcrypt" in after.lower()):
            descriptions.append("Fixed plaintext password storage")
        if "try" not in before and "try" in after:
            descriptions.append("Added error handling")
        if "async" not in before and "async" in after:
            descriptions.append("Converted to async for better performance")
        if not descriptions:
            descriptions.append(f"Code improvement in {language}")
        return ". ".join(descriptions)

    def _auto_tag(self, before: str, after: str) -> List[str]:
        """Auto-generate tags based on code patterns."""
        tags = []
        combined = before + after
        if re.search(r'(SELECT|INSERT|UPDATE|DELETE)', combined):
            tags.append("sql")
        if re.search(r'(eval|exec|system)', combined):
            tags.append("injection")
        if re.search(r'(password|secret|token|key)', combined, re.I):
            tags.append("credentials")
        if re.search(r'(async|await|promise|thread)', combined, re.I):
            tags.append("concurrency")
        if re.search(r'(try|catch|except|finally)', combined):
            tags.append("error-handling")
        if re.search(r'(aria-|role=|alt=)', combined):
            tags.append("accessibility")
        if re.search(r'(cache|memo|lazy)', combined, re.I):
            tags.append("performance")
        return tags or ["general"]

    def _compute_confidence(self, before: str, after: str) -> float:
        """Compute confidence that the fix is meaningful."""
        if not before.strip() or not after.strip():
            return 0.3
        if before.strip() == after.strip():
            return 0.1
        # More lines changed = less confident it's a focused fix
        before_lines = len(before.splitlines())
        after_lines = len(after.splitlines())
        size_ratio = min(before_lines, after_lines) / max(before_lines, after_lines, 1)
        return min(0.5 + size_ratio * 0.4, 0.95)

    def search_nuggets(
        self,
        query: str,
        language: Optional[str] = None,
        pattern_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[WisdomNugget]:
        """Search stored nuggets by similarity."""
        results = []
        query_lower = query.lower()
        for nugget in self._nuggets.values():
            if language and nugget.language != language:
                continue
            if pattern_type and nugget.pattern_type != pattern_type:
                continue
            # Simple text similarity
            score = 0.0
            combined = (nugget.before_snippet + nugget.after_snippet + nugget.description).lower()
            query_words = query_lower.split()
            for word in query_words:
                if word in combined:
                    score += 1.0 / len(query_words)
            # Tag match bonus
            for tag in nugget.tags:
                if tag in query_lower:
                    score += 0.2
            if score > 0.1:
                nugget_copy = WisdomNugget(
                    nugget_id=nugget.nugget_id,
                    pattern_type=nugget.pattern_type,
                    language=nugget.language,
                    before_snippet=nugget.before_snippet,
                    after_snippet=nugget.after_snippet,
                    description=nugget.description,
                    tags=nugget.tags,
                    source_project=nugget.source_project,
                    created_at=nugget.created_at,
                    usage_count=nugget.usage_count,
                    confidence=score,
                )
                results.append(nugget_copy)
        results.sort(key=lambda n: n.confidence, reverse=True)
        return results[:limit]

    def get_all_nuggets(self) -> List[WisdomNugget]:
        return list(self._nuggets.values())

    def get_stats(self) -> Dict[str, Any]:
        nuggets = list(self._nuggets.values())
        by_type: Dict[str, int] = {}
        by_lang: Dict[str, int] = {}
        for n in nuggets:
            by_type[n.pattern_type] = by_type.get(n.pattern_type, 0) + 1
            by_lang[n.language] = by_lang.get(n.language, 0) + 1
        return {
            "totalNuggets": len(nuggets),
            "byType": by_type,
            "byLanguage": by_lang,
            "totalUsages": sum(n.usage_count for n in nuggets),
        }


_extractor_singleton: Optional[PatternExtractor] = None


def get_pattern_extractor() -> PatternExtractor:
    global _extractor_singleton
    if _extractor_singleton is None:
        _extractor_singleton = PatternExtractor()
    return _extractor_singleton
