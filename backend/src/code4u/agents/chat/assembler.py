"""Context Assembly — token-budgeted prompt builder for Code Chat.

Takes a ``RetrievedContext`` from the graph retriever and formats it
into a structured prompt using XML tags that help the LLM navigate
the code.

Key design decisions:

- **"Lost in the Middle" prevention:** The most important code
  (entry points) goes at the TOP and the user's question goes at
  the BOTTOM of the prompt, so the LLM doesn't lose focus.

- **Token budgeting:** A ``TokenBudgeter`` prioritizes content in
  strict order: (1) current file, (2) direct dependencies (1-hop),
  (3) transitive dependencies (2-hop), (4) documentation.  It stops
  just before the context window overflows.

- **XML structure:** Uses ``<file path='...'>`` and
  ``<dependency_graph>`` tags so the LLM can parse the context
  programmatically rather than guessing at boundaries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from code4u.agents.chat.retriever import RetrievedContext, GraphNode

logger = structlog.get_logger("assembler")

# Rough token estimation: 1 token ≈ 4 characters for code
_CHARS_PER_TOKEN = 4


@dataclass
class AssembledPrompt:
    """The final assembled prompt ready for the LLM."""
    system_message: str
    user_prompt: str
    context_files: int = 0
    context_symbols: int = 0
    estimated_tokens: int = 0
    budget_used_pct: float = 0.0
    truncated_files: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "systemMessage": self.system_message,
            "userPrompt": self.user_prompt[:200] + "...",
            "contextFiles": self.context_files,
            "contextSymbols": self.context_symbols,
            "estimatedTokens": self.estimated_tokens,
            "budgetUsedPct": round(self.budget_used_pct, 1),
            "truncatedFiles": self.truncated_files,
        }


class TokenBudgeter:
    """Manages token allocation across context tiers.

    Priority tiers (high to low):
      1. Entry-point files (direct matches)
      2. Hop-1 dependencies (direct upstream/downstream)
      3. Hop-2 transitive dependencies
      4. Graph metadata (dependency tree, bottlenecks)

    Each tier gets a share of the remaining budget.  If a tier
    exceeds its allocation, individual files are truncated.
    """

    def __init__(self, max_tokens: int = 8000) -> None:
        self._max_tokens = max_tokens
        self._used_tokens = 0
        self._truncated: List[str] = []

    @property
    def remaining(self) -> int:
        return max(0, self._max_tokens - self._used_tokens)

    @property
    def used_pct(self) -> float:
        if self._max_tokens == 0:
            return 100.0
        return (self._used_tokens / self._max_tokens) * 100

    def estimate_tokens(self, text: str) -> int:
        return len(text) // _CHARS_PER_TOKEN

    def consume(self, text: str) -> str:
        """Consume tokens.  If over budget, truncate and note it."""
        tokens = self.estimate_tokens(text)
        if tokens <= self.remaining:
            self._used_tokens += tokens
            return text
        # Truncate to fit
        allowed_chars = self.remaining * _CHARS_PER_TOKEN
        if allowed_chars < 100:
            return ""
        truncated = text[:allowed_chars] + "\n... [truncated — token budget exceeded]\n"
        self._used_tokens = self._max_tokens
        return truncated

    def try_add_file(self, file_path: str, content: str) -> Optional[str]:
        """Try to add a file's content within the budget.

        Returns the (possibly truncated) content, or None if no
        budget remains at all.
        """
        if self.remaining <= 0:
            self._truncated.append(file_path)
            return None

        tokens = self.estimate_tokens(content)
        if tokens <= self.remaining:
            self._used_tokens += tokens
            return content

        allowed_chars = self.remaining * _CHARS_PER_TOKEN
        if allowed_chars < 80:
            self._truncated.append(file_path)
            return None

        self._truncated.append(file_path)
        truncated = content[:allowed_chars] + "\n... [truncated]\n"
        self._used_tokens = self._max_tokens
        return truncated


def _read_file_safe(file_path: str) -> str:
    """Read a file, returning empty string on any error."""
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except Exception:
        return ""


def _format_dependency_graph(ctx: RetrievedContext) -> str:
    """Format the dependency graph as a human-readable tree."""
    lines = ["<dependency_graph>"]

    entry_nodes = [n for n in ctx.graph_nodes if n.relationship == "entry_point"]
    upstream_nodes = [n for n in ctx.graph_nodes if n.relationship == "upstream"]
    downstream_nodes = [n for n in ctx.graph_nodes if n.relationship == "downstream"]
    transitive_nodes = [n for n in ctx.graph_nodes if n.relationship == "transitive"]

    if entry_nodes:
        lines.append("  Entry Points:")
        for n in entry_nodes:
            name = Path(n.file_path).name
            syms = ", ".join(n.symbols[:5])
            lines.append(f"    [{name}] defines: {syms}")

    if upstream_nodes:
        lines.append("  Upstream Dependencies (imports from):")
        for n in upstream_nodes:
            name = Path(n.file_path).name
            syms = ", ".join(n.symbols[:5])
            lines.append(f"    ← [{name}] provides: {syms}")

    if downstream_nodes:
        lines.append("  Downstream Callers (imported by):")
        for n in downstream_nodes:
            name = Path(n.file_path).name
            syms = ", ".join(n.symbols[:5])
            lines.append(f"    → [{name}] uses: {syms}")

    if transitive_nodes:
        lines.append("  Transitive (2-hop):")
        for n in transitive_nodes:
            name = Path(n.file_path).name
            lines.append(f"    ⇢ [{name}]")

    if ctx.bottleneck_files:
        lines.append("  Bottleneck Modules (high fan-out):")
        for fp in ctx.bottleneck_files:
            lines.append(f"    ⚠ [{Path(fp).name}]")

    lines.append("</dependency_graph>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ContextAssembler
# ---------------------------------------------------------------------------

class ContextAssembler:
    """Assembles a token-budgeted, graph-augmented prompt.

    Uses the "Lost in the Middle" layout:
      - TOP: most important code (entry points)
      - MIDDLE: supporting context (dependencies)
      - BOTTOM: user query (recency bias ensures the LLM focuses on it)
    """

    def __init__(
        self,
        *,
        max_context_tokens: int = 8000,
        include_line_numbers: bool = True,
    ) -> None:
        self._max_tokens = max_context_tokens
        self._line_numbers = include_line_numbers

    def assemble(
        self,
        ctx: RetrievedContext,
        *,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> AssembledPrompt:
        """Build the final prompt from retrieved context.

        Layout (top to bottom):
          1. System message (architect persona)
          2. Dependency graph overview
          3. Entry-point file contents (most relevant)
          4. Hop-1 file contents
          5. Hop-2 file contents (if budget allows)
          6. Conversation history (if any)
          7. User's current query
        """
        budgeter = TokenBudgeter(max_tokens=self._max_tokens)
        system_msg = self._build_system_message(ctx)
        parts: List[str] = []

        # Section 1: Graph overview (compact, always fits)
        graph_text = _format_dependency_graph(ctx)
        graph_text = budgeter.consume(graph_text)
        if graph_text:
            parts.append(graph_text)

        # Section 2: Entry-point files (highest priority)
        entry_files = [n for n in ctx.graph_nodes if n.hop_distance == 0]
        for node in entry_files:
            content = _read_file_safe(node.file_path)
            if not content:
                continue
            formatted = self._format_file_block(node.file_path, content)
            result = budgeter.try_add_file(node.file_path, formatted)
            if result:
                parts.append(result)

        # Section 3: Hop-1 files (direct deps)
        hop1_files = sorted(
            [n for n in ctx.graph_nodes if n.hop_distance == 1],
            key=lambda n: -n.relevance,
        )
        for node in hop1_files:
            content = _read_file_safe(node.file_path)
            if not content:
                continue
            formatted = self._format_file_block(node.file_path, content)
            result = budgeter.try_add_file(node.file_path, formatted)
            if result:
                parts.append(result)

        # Section 4: Hop-2 files (only if budget allows)
        hop2_files = sorted(
            [n for n in ctx.graph_nodes if n.hop_distance >= 2],
            key=lambda n: -n.relevance,
        )
        for node in hop2_files:
            if budgeter.remaining < 200:
                budgeter._truncated.append(node.file_path)
                continue
            content = _read_file_safe(node.file_path)
            if not content:
                continue
            formatted = self._format_file_block(node.file_path, content)
            result = budgeter.try_add_file(node.file_path, formatted)
            if result:
                parts.append(result)

        # Section 5: Conversation history
        if conversation_history:
            history_text = self._format_history(conversation_history)
            history_text = budgeter.consume(history_text)
            if history_text:
                parts.append(history_text)

        # Section 6: User query (BOTTOM — recency bias)
        parts.append(f"\n<user_question>\n{ctx.query}\n</user_question>")

        user_prompt = "\n\n".join(parts)

        result = AssembledPrompt(
            system_message=system_msg,
            user_prompt=user_prompt,
            context_files=len([n for n in ctx.graph_nodes if n.file_path not in budgeter._truncated]),
            context_symbols=ctx.total_symbols,
            estimated_tokens=budgeter._used_tokens + budgeter.estimate_tokens(system_msg),
            budget_used_pct=budgeter.used_pct,
            truncated_files=budgeter._truncated,
        )

        logger.info(
            "context_assembled",
            files=result.context_files,
            tokens=result.estimated_tokens,
            budget_pct=round(result.budget_used_pct, 1),
            truncated=len(result.truncated_files),
        )

        return result

    def _build_system_message(self, ctx: RetrievedContext) -> str:
        """Build a system prompt with architectural awareness."""
        bottleneck_note = ""
        if ctx.bottleneck_files:
            names = [Path(f).name for f in ctx.bottleneck_files[:3]]
            bottleneck_note = (
                f" The following modules are architectural bottlenecks "
                f"(many other files depend on them): {', '.join(names)}. "
                f"Changes to these modules have a high blast radius."
            )

        cycle_note = ""
        if ctx.cycles_detected:
            cycle_note = (
                f" Warning: {len(ctx.cycles_detected)} circular dependency "
                f"chain(s) were detected in the codebase."
            )

        return (
            "You are a senior software architect analyzing a codebase. "
            "You have been given the dependency graph and source code of the "
            "most relevant files. Use the <dependency_graph> to understand "
            "how files relate to each other. Use <file> blocks to read the "
            "actual implementation. "
            "When explaining code, always mention which file and which "
            "function/class you are referring to. "
            "If the user asks about changing something, identify all files "
            "that would be affected using the dependency graph."
            f"{bottleneck_note}{cycle_note}"
        )

    def _format_file_block(self, file_path: str, content: str) -> str:
        """Format a file as an XML block with optional line numbers."""
        rel = Path(file_path).name
        if self._line_numbers:
            lines = content.splitlines()
            numbered = "\n".join(
                f"{i + 1:4d} | {line}" for i, line in enumerate(lines)
            )
            return f"<file path=\"{rel}\">\n{numbered}\n</file>"
        return f"<file path=\"{rel}\">\n{content}\n</file>"

    def _format_history(self, history: List[Dict[str, str]]) -> str:
        """Format conversation history."""
        parts = ["<conversation_history>"]
        for msg in history[-6:]:  # Keep last 6 messages
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if len(content) > 500:
                content = content[:500] + "..."
            parts.append(f"  <{role}>{content}</{role}>")
        parts.append("</conversation_history>")
        return "\n".join(parts)
