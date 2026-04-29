"""Visual Grounding — map an image to codebase symbols.

Takes an uploaded image (base64-encoded) and the workspace's
``DependencyMap`` to identify which files and symbols are visually
represented.  The vision LLM sees the image alongside a structured
summary of the codebase and returns a grounded mapping.

Supports:
  - UI screenshots → React/JSX/CSS component identification
  - Architecture diagrams → Python/TS module identification
  - Whiteboard sketches → dependency relationship proposals

Usage::

    grounder = VisualGrounder(llm_client, dep_map)
    result = await grounder.ground(image_b64, intent)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from code4u.ai_engine.llm.client import LLMClient, LLMRequest
from code4u.code_intelligence.knowledge_graph.symbol_indexer import DependencyMap

logger = structlog.get_logger("visual_grounder")

_UI_EXTENSIONS = frozenset({".tsx", ".jsx", ".css", ".scss", ".vue", ".svelte", ".html"})
_ALL_CODE_EXTENSIONS = frozenset({
    ".py", ".ts", ".tsx", ".js", ".jsx", ".css", ".scss",
    ".vue", ".svelte", ".html", ".go", ".rs", ".java",
})


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class GroundedSymbol:
    """A single symbol matched by visual reasoning."""
    name: str
    file_path: str
    kind: str
    confidence: float
    visual_role: str


@dataclass
class GroundingResult:
    """Complete result of a visual grounding operation."""
    matched_files: List[str] = field(default_factory=list)
    matched_symbols: List[GroundedSymbol] = field(default_factory=list)
    visual_summary: str = ""
    suggested_intent: str = ""
    is_ui_layout: bool = False
    raw_llm_response: str = ""

    @property
    def metadata(self) -> Dict[str, Any]:
        return {
            "matchedFiles": self.matched_files,
            "matchedSymbols": [
                {
                    "name": s.name,
                    "filePath": s.file_path,
                    "kind": s.kind,
                    "confidence": s.confidence,
                    "visualRole": s.visual_role,
                }
                for s in self.matched_symbols
            ],
            "visualSummary": self.visual_summary,
            "suggestedIntent": self.suggested_intent,
            "isUiLayout": self.is_ui_layout,
        }


# ---------------------------------------------------------------------------
# Codebase summary builder
# ---------------------------------------------------------------------------

def build_codebase_summary(dep_map: DependencyMap, max_files: int = 200) -> str:
    """Build a compact text summary of the codebase for the vision prompt.

    Groups files by directory, listing top-level symbol names for each
    file.  Only includes files with extensions in ``_ALL_CODE_EXTENSIONS``.
    """
    by_dir: Dict[str, List[Dict[str, Any]]] = {}
    file_count = 0

    for file_path, symbols in dep_map._file_symbols.items():
        if file_count >= max_files:
            break
        ext = Path(file_path).suffix.lower()
        if ext not in _ALL_CODE_EXTENSIONS:
            continue
        parent = str(Path(file_path).parent)
        short_name = Path(file_path).name
        sym_names = [s.name for s in symbols[:15]]
        by_dir.setdefault(parent, []).append({
            "file": short_name,
            "symbols": sym_names,
            "ext": ext,
        })
        file_count += 1

    lines: List[str] = []
    for directory, files in sorted(by_dir.items()):
        short_dir = "/".join(Path(directory).parts[-3:])
        lines.append(f"\n## {short_dir}/")
        for f in sorted(files, key=lambda x: x["file"]):
            syms = ", ".join(f["symbols"][:10])
            if syms:
                lines.append(f"  - {f['file']}: {syms}")
            else:
                lines.append(f"  - {f['file']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_GROUNDING_SYSTEM = """\
You are a Visual Code Grounding expert. You analyze images (UI screenshots, \
architecture diagrams, whiteboard sketches) and map visual elements to \
specific files and symbols in a codebase.

You always respond with valid JSON matching this schema:
{
  "visual_summary": "Brief description of what the image shows",
  "is_ui_layout": true/false,
  "suggested_intent": "What refactor the user likely wants",
  "matched_files": ["path/to/file.tsx", ...],
  "matched_symbols": [
    {
      "name": "ComponentName",
      "file": "path/to/file.tsx",
      "kind": "function|class|component|variable",
      "confidence": 0.0-1.0,
      "visual_role": "What this symbol represents in the image"
    }
  ]
}

Rules:
- Match symbols from the provided codebase structure ONLY.
- Confidence: 0.9+ for exact name matches, 0.7+ for likely matches, \
0.5+ for related.
- is_ui_layout: true if the image shows a UI/layout change.
- Be specific about file paths — use the exact paths from the codebase summary.
"""

_GROUNDING_USER_TEMPLATE = """\
## User Intent
"{intent}"

## Codebase Structure
{codebase_summary}

## Task
Look at the attached image and the codebase structure above. \
Identify which files and symbols from the codebase are most likely \
represented in or affected by the visual elements in the image.

If this is a UI screenshot, focus on component files (.tsx, .jsx, .vue, .css). \
If this is an architecture diagram, focus on module files (.py, .ts). \
If this is a whiteboard sketch with arrows, suggest dependency relationships.

Respond with JSON only.
"""


# ---------------------------------------------------------------------------
# VisualGrounder
# ---------------------------------------------------------------------------

class VisualGrounder:
    """Maps an uploaded image to codebase symbols using a vision LLM."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        dep_map: Optional[DependencyMap] = None,
    ):
        self._llm = llm_client or LLMClient()
        self._dep_map = dep_map

    async def ground(
        self,
        image_base64: str,
        intent: str = "",
        dep_map: Optional[DependencyMap] = None,
        media_type: str = "image/png",
    ) -> GroundingResult:
        """Analyze an image against the codebase and return grounded symbols.

        Args:
            image_base64: Base64-encoded image data (no data-URI prefix).
            intent: Optional user intent string for context.
            dep_map: Override the default DependencyMap.
            media_type: MIME type of the image.

        Returns:
            A ``GroundingResult`` with matched files and symbols.
        """
        dm = dep_map or self._dep_map
        if dm is None:
            return GroundingResult(
                visual_summary="No DependencyMap available for grounding."
            )

        codebase_summary = build_codebase_summary(dm)
        user_text = _GROUNDING_USER_TEMPLATE.format(
            intent=intent or "Identify visual elements and map to code",
            codebase_summary=codebase_summary,
        )

        provider = self._llm.provider

        if provider == "local":
            return self._ground_local(intent, dm)

        if provider == "anthropic":
            messages = self._build_anthropic_messages(
                user_text, image_base64, media_type
            )
        else:
            messages = self._build_openai_messages(
                user_text, image_base64, media_type
            )

        request = LLMRequest(
            messages=messages,
            temperature=0.0,
            max_tokens=4096,
        )

        try:
            response = await self._llm.generate(request)
            return self._parse_response(response.content, dm)
        except Exception as exc:
            logger.error("visual_grounding_failed", error=str(exc))
            return GroundingResult(
                visual_summary=f"Vision LLM error: {exc}",
                raw_llm_response=str(exc),
            )

    # -- Message builders for multi-modal APIs --------------------------------

    @staticmethod
    def _build_openai_messages(
        user_text: str,
        image_b64: str,
        media_type: str,
    ) -> list:
        """Build OpenAI-format messages with inline image."""
        return [
            {"role": "system", "content": _GROUNDING_SYSTEM},
            {
                "role": "user",
                "content": json.dumps([
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{image_b64}",
                        },
                    },
                    {"type": "text", "text": user_text},
                ]),
            },
        ]

    @staticmethod
    def _build_anthropic_messages(
        user_text: str,
        image_b64: str,
        media_type: str,
    ) -> list:
        """Build Anthropic-format messages with inline image."""
        return [
            {"role": "system", "content": _GROUNDING_SYSTEM},
            {
                "role": "user",
                "content": json.dumps([
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": user_text},
                ]),
            },
        ]

    # -- Response parsing ------------------------------------------------------

    def _parse_response(
        self,
        raw: str,
        dep_map: DependencyMap,
    ) -> GroundingResult:
        """Parse the vision LLM's JSON response into a GroundingResult."""
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not json_match:
            return GroundingResult(
                visual_summary="Could not parse vision response.",
                raw_llm_response=raw,
            )

        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError:
            return GroundingResult(
                visual_summary="Invalid JSON from vision LLM.",
                raw_llm_response=raw,
            )

        matched_files = self._resolve_files(
            data.get("matched_files", []), dep_map
        )

        matched_symbols: List[GroundedSymbol] = []
        for sym_data in data.get("matched_symbols", []):
            matched_symbols.append(GroundedSymbol(
                name=sym_data.get("name", ""),
                file_path=sym_data.get("file", ""),
                kind=sym_data.get("kind", "unknown"),
                confidence=float(sym_data.get("confidence", 0.5)),
                visual_role=sym_data.get("visual_role", ""),
            ))

        return GroundingResult(
            matched_files=matched_files,
            matched_symbols=matched_symbols,
            visual_summary=data.get("visual_summary", ""),
            suggested_intent=data.get("suggested_intent", ""),
            is_ui_layout=bool(data.get("is_ui_layout", False)),
            raw_llm_response=raw,
        )

    @staticmethod
    def _resolve_files(
        file_hints: List[str],
        dep_map: DependencyMap,
    ) -> List[str]:
        """Resolve LLM-returned file paths against actual indexed files.

        The LLM may return short names (``Header.tsx``) or partial paths
        (``components/Header.tsx``).  We match against the full set of
        indexed file paths and return the real absolute paths.
        """
        indexed = set(dep_map._file_symbols.keys()) | set(dep_map._imports.keys())
        resolved: List[str] = []

        for hint in file_hints:
            hint_lower = hint.lower().replace("\\", "/")
            for real_path in indexed:
                real_lower = real_path.lower().replace("\\", "/")
                if real_lower.endswith(hint_lower) or hint_lower in real_lower:
                    if real_path not in resolved:
                        resolved.append(real_path)
                    break
        return resolved

    # -- Local fallback -------------------------------------------------------

    def _ground_local(
        self,
        intent: str,
        dep_map: DependencyMap,
    ) -> GroundingResult:
        """Deterministic local grounding (no vision LLM).

        Matches based on keyword analysis of the intent string against
        symbol names and file names in the DependencyMap.  Prioritises
        UI files (.tsx, .jsx, .css) when the intent mentions UI terms.
        """
        intent_lower = intent.lower()
        ui_keywords = {"header", "footer", "sidebar", "navbar", "nav",
                       "menu", "button", "card", "modal", "layout",
                       "page", "form", "input", "table", "list", "grid",
                       "dashboard", "panel", "tab", "dialog", "app"}

        is_ui = any(
            re.search(rf"\b{kw}\b", intent_lower) for kw in ui_keywords
        )

        intent_tokens = set(re.findall(r"[a-z][a-z0-9]*", intent_lower))
        intent_compounds = set(re.findall(r"[a-z_]+", intent_lower))

        scored_files: List[tuple] = []
        scored_symbols: List[GroundedSymbol] = []

        for file_path, symbols in dep_map._file_symbols.items():
            ext = Path(file_path).suffix.lower()
            file_name = Path(file_path).stem.lower()
            file_words = set(re.findall(r"[a-z][a-z0-9]*", file_name))

            overlap = intent_tokens & file_words
            if not overlap:
                for sym in symbols:
                    sym_lower = sym.name.lower()
                    sym_words = set(re.findall(r"[a-z][a-z0-9]*", sym_lower))
                    compound_match = sym_lower in intent_compounds or sym_lower in intent_lower
                    if intent_tokens & sym_words or compound_match:
                        overlap = intent_tokens & sym_words or {sym_lower}
                        break

            if not overlap:
                continue

            score = len(overlap) / max(len(intent_tokens), 1)
            if is_ui and ext in _UI_EXTENSIONS:
                score += 0.3
            scored_files.append((file_path, score))

            for sym in symbols:
                sym_lower = sym.name.lower()
                sym_words = set(re.findall(r"[a-z][a-z0-9]*", sym_lower))
                compound_match = sym_lower in intent_compounds or sym_lower in intent_lower
                sym_overlap = intent_tokens & sym_words
                if sym_overlap or compound_match:
                    matched = sym_overlap or {sym_lower}
                    s = len(matched) / max(len(intent_tokens), 1)
                    if is_ui and ext in _UI_EXTENSIONS:
                        s += 0.2
                    scored_symbols.append(GroundedSymbol(
                        name=sym.name,
                        file_path=file_path,
                        kind=sym.kind,
                        confidence=min(s, 1.0),
                        visual_role=f"Matched via keyword: {', '.join(matched)}",
                    ))

        scored_files.sort(key=lambda x: -x[1])
        scored_symbols.sort(key=lambda x: -x.confidence)

        return GroundingResult(
            matched_files=[f for f, _ in scored_files[:10]],
            matched_symbols=scored_symbols[:15],
            visual_summary=f"Local grounding (keyword): matched {len(scored_files)} files",
            suggested_intent=intent,
            is_ui_layout=is_ui,
        )
