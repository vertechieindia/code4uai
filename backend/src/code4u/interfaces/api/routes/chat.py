"""Chat API — Graph-Augmented Code Chat.

Endpoints:
  - ``POST /chat/query``      — ask a question about the codebase.
  - ``GET  /chat/context``     — preview the retrieved context (debug).
  - ``POST /chat/sessions``    — create a new chat session.
  - ``GET  /chat/sessions``    — list active chat sessions.
  - ``DELETE /chat/sessions/{id}`` — delete a chat session.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import structlog

from code4u.agents.chat.retriever import ContextRetriever, RetrievedContext
from code4u.agents.chat.assembler import ContextAssembler, AssembledPrompt

logger = structlog.get_logger("chat")

router = APIRouter()


# ---------------------------------------------------------------------------
# In-memory chat session store
# ---------------------------------------------------------------------------

class _ChatSession:
    """A single conversation with history."""

    def __init__(self, session_id: str, workspace_path: str):
        self.id = session_id
        self.workspace_path = workspace_path
        self.messages: List[Dict[str, str]] = []
        self.created_at = time.time()
        self.last_query_at = time.time()

    def add_user(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})
        self.last_query_at = time.time()

    def add_assistant(self, content: str) -> None:
        self.messages.append({"role": "assistant", "content": content})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "workspacePath": self.workspace_path,
            "messageCount": len(self.messages),
            "createdAt": self.created_at,
            "lastQueryAt": self.last_query_at,
        }


_sessions: Dict[str, _ChatSession] = {}

# Cached dep maps per workspace (avoid re-indexing on every query)
_dep_map_cache: Dict[str, Any] = {}


def _get_dep_map(workspace_path: str) -> Any:
    """Get or build a DependencyMap for the workspace."""
    if workspace_path in _dep_map_cache:
        return _dep_map_cache[workspace_path]

    from code4u.code_intelligence.knowledge_graph.symbol_indexer import SymbolIndexer
    indexer = SymbolIndexer()
    dep_map = indexer.index_workspace(workspace_path)
    _dep_map_cache[workspace_path] = dep_map
    return dep_map


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ChatQueryRequest(BaseModel):
    query: str = Field(..., description="The question about the codebase.")
    workspacePath: str = Field(..., description="Workspace root to analyze.")
    sessionId: Optional[str] = Field(None, description="Session ID for conversation continuity.")
    maxContextTokens: int = Field(8000, description="Token budget for context.")
    maxHops: int = Field(2, ge=1, le=4, description="Graph traversal depth.")
    maxFiles: int = Field(20, ge=1, le=50, description="Maximum context files.")
    includeLineNumbers: bool = Field(True, description="Include line numbers in code blocks.")


class ContextPreviewRequest(BaseModel):
    query: str = Field(..., description="The question to preview context for.")
    workspacePath: str = Field(..., description="Workspace root.")
    maxHops: int = Field(2, ge=1, le=4)
    maxFiles: int = Field(20, ge=1, le=50)


class CreateSessionRequest(BaseModel):
    workspacePath: str = Field(..., description="Workspace root for this session.")


# ---------------------------------------------------------------------------
# POST /chat/query
# ---------------------------------------------------------------------------

@router.post("/chat/query")
async def chat_query(request: ChatQueryRequest):
    """Ask a question about the codebase with graph-augmented context.

    The system:
      1. Extracts keywords from your query.
      2. Finds matching symbols in the DependencyMap.
      3. Performs a 2-hop graph traversal for full context.
      4. Assembles a token-budgeted prompt.
      5. Sends it to the LLM (or returns the context in local mode).

    Example queries:
      - "How does the payment flow work?"
      - "What will break if I change UserProfile?"
      - "Explain the authentication middleware"
    """
    t0 = time.time()

    query_lower = request.query.strip().lower()
    if query_lower.startswith("/optimize") or query_lower.startswith("optimize "):
        return await _handle_optimize_intent(request, t0)
    if query_lower.startswith("/upgrade-library") or query_lower.startswith("/migrate"):
        return await _handle_upgrade_intent(request, t0)

    dep_map = _get_dep_map(request.workspacePath)

    retriever = ContextRetriever(
        dep_map,
        max_hops=request.maxHops,
        max_files=request.maxFiles,
    )
    ctx = retriever.retrieve(request.query)

    # Get or create session
    session = None
    if request.sessionId and request.sessionId in _sessions:
        session = _sessions[request.sessionId]
    elif request.sessionId is None:
        sid = str(uuid.uuid4())[:8]
        session = _ChatSession(sid, request.workspacePath)
        _sessions[sid] = session
    else:
        sid = request.sessionId
        session = _ChatSession(sid, request.workspacePath)
        _sessions[sid] = session

    session.add_user(request.query)

    assembler = ContextAssembler(
        max_context_tokens=request.maxContextTokens,
        include_line_numbers=request.includeLineNumbers,
    )
    assembled = assembler.assemble(
        ctx,
        conversation_history=session.messages[:-1],  # exclude current query
    )

    # Attempt LLM call; fall back to context-only response
    answer = _generate_answer(assembled, ctx)
    session.add_assistant(answer)

    elapsed = (time.time() - t0) * 1000

    return {
        "answer": answer,
        "sessionId": session.id,
        "context": {
            "filesUsed": assembled.context_files,
            "symbolsUsed": assembled.context_symbols,
            "estimatedTokens": assembled.estimated_tokens,
            "budgetUsedPct": round(assembled.budget_used_pct, 1),
            "truncatedFiles": assembled.truncated_files,
            "entryPoints": [
                {"name": ep.name, "kind": ep.kind, "file": ep.file_path, "score": ep.score}
                for ep in ctx.entry_points
            ],
            "graphNodes": len(ctx.graph_nodes),
            "bottlenecks": ctx.bottleneck_files,
        },
        "durationMs": round(elapsed, 1),
    }


# ---------------------------------------------------------------------------
# GET /chat/context  (debug / preview)
# ---------------------------------------------------------------------------

@router.post("/chat/context")
async def preview_context(request: ContextPreviewRequest):
    """Preview the retrieved context without calling the LLM.

    Useful for debugging and understanding what the retriever found.
    """
    dep_map = _get_dep_map(request.workspacePath)

    retriever = ContextRetriever(
        dep_map,
        max_hops=request.maxHops,
        max_files=request.maxFiles,
    )
    ctx = retriever.retrieve(request.query)

    assembler = ContextAssembler(max_context_tokens=8000)
    assembled = assembler.assemble(ctx)

    return {
        "retrievedContext": ctx.to_dict(),
        "assembledPrompt": assembled.to_dict(),
        "systemMessage": assembled.system_message,
    }


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

@router.post("/chat/sessions")
async def create_session(request: CreateSessionRequest):
    """Create a new chat session."""
    sid = str(uuid.uuid4())[:8]
    session = _ChatSession(sid, request.workspacePath)
    _sessions[sid] = session
    return {"sessionId": sid, "workspacePath": request.workspacePath}


@router.get("/chat/sessions")
async def list_sessions():
    """List all active chat sessions."""
    return {
        "sessions": [s.to_dict() for s in _sessions.values()],
        "count": len(_sessions),
    }


@router.delete("/chat/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session and its history."""
    if session_id not in _sessions:
        raise HTTPException(404, f"Session {session_id} not found.")
    del _sessions[session_id]
    return {"status": "deleted", "sessionId": session_id}


# ---------------------------------------------------------------------------
# LLM integration (local fallback)
# ---------------------------------------------------------------------------

def _generate_answer(assembled: AssembledPrompt, ctx: RetrievedContext) -> str:
    """Generate an answer using the SmartRouter, or fall back to
    a structured local summary if no LLM is available.
    """
    try:
        return _call_llm(assembled)
    except Exception:
        return _local_summary(ctx, assembled)


def _call_llm(assembled: AssembledPrompt) -> str:
    """Attempt to call the LLM via the SmartRouter."""
    raise NotImplementedError("LLM call — use local summary fallback")


def _local_summary(ctx: RetrievedContext, assembled: AssembledPrompt) -> str:
    """Generate a structured summary without an LLM.

    This provides genuine value even without an API key:
    the graph context tells the user *exactly* which files are
    involved and how they relate.
    """
    parts: List[str] = []

    parts.append(f"**Graph-Augmented Analysis for:** \"{ctx.query}\"\n")

    if ctx.entry_points:
        parts.append("**Entry Points Found:**")
        for ep in ctx.entry_points[:5]:
            from pathlib import Path
            fname = Path(ep.file_path).name
            parts.append(f"- `{ep.name}` ({ep.kind}) in `{fname}` (relevance: {ep.score:.1f})")
        parts.append("")

    entry_nodes = [n for n in ctx.graph_nodes if n.relationship == "entry_point"]
    upstream = [n for n in ctx.graph_nodes if n.relationship == "upstream"]
    downstream = [n for n in ctx.graph_nodes if n.relationship == "downstream"]
    transitive = [n for n in ctx.graph_nodes if n.relationship == "transitive"]

    if upstream:
        parts.append("**Upstream Dependencies (these files provide functionality):**")
        for n in upstream:
            from pathlib import Path
            parts.append(f"- `{Path(n.file_path).name}` — defines: {', '.join(n.symbols[:5])}")
        parts.append("")

    if downstream:
        parts.append("**Downstream Callers (these files will break if you change the entry points):**")
        for n in downstream:
            from pathlib import Path
            parts.append(f"- `{Path(n.file_path).name}` — uses: {', '.join(n.symbols[:5])}")
        parts.append("")

    if transitive:
        parts.append(f"**Transitive Dependencies ({len(transitive)} files, 2 hops away):**")
        for n in transitive[:5]:
            from pathlib import Path
            parts.append(f"- `{Path(n.file_path).name}`")
        parts.append("")

    if ctx.bottleneck_files:
        parts.append("**Bottleneck Modules (high blast radius — change with care):**")
        for fp in ctx.bottleneck_files:
            from pathlib import Path
            parts.append(f"- `{Path(fp).name}`")
        parts.append("")

    parts.append(
        f"*Context: {ctx.total_files} files, {ctx.total_symbols} symbols, "
        f"{ctx.hops_performed}-hop traversal, "
        f"{assembled.estimated_tokens} estimated tokens.*"
    )

    return "\n".join(parts)


async def _handle_optimize_intent(request: ChatQueryRequest, t0: float):
    """Handle /optimize command in chat — scan workspace for anti-patterns."""
    import os
    from code4u.agents.performance.optimizer import Optimizer

    workspace = request.workspacePath
    optimizer = Optimizer()

    skip = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"}
    findings = []
    scanned = 0

    if os.path.isdir(workspace):
        for root, dirs, files in os.walk(workspace):
            dirs[:] = [d for d in dirs if d not in skip]
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in (".py", ".ts", ".tsx", ".js", ".jsx"):
                    continue
                if scanned >= 20:
                    break
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", errors="ignore") as f:
                        source = f.read()
                except Exception:
                    continue
                if len(source) < 30:
                    continue
                scanned += 1
                smells = optimizer.scan_source(source, os.path.relpath(fpath, workspace))
                for s in smells:
                    findings.append(s)
            if scanned >= 20:
                break

    elapsed = (time.time() - t0) * 1000

    if not findings:
        answer = (
            "**Optimization Scan Complete** — No performance anti-patterns detected "
            f"in {scanned} files. Your code looks efficient!\n\n"
            "*Tip: You can also use the Performance panel (Perf tab in footer) for "
            "deeper analysis with profiling.*"
        )
    else:
        parts = [
            f"**Optimization Scan** — Found **{len(findings)}** performance issues "
            f"in {scanned} files:\n"
        ]
        for s in findings[:10]:
            severity_icon = {"critical": "🔴", "warning": "🟠", "info": "🔵"}.get(
                getattr(s, "severity", "info"), "⚪"
            )
            parts.append(
                f"{severity_icon} **{getattr(s, 'category', 'Issue')}** "
                f"in `{getattr(s, 'file_path', '?')}` line {getattr(s, 'line_number', '?')}\n"
                f"  {getattr(s, 'description', '')}\n"
            )
        if len(findings) > 10:
            parts.append(f"\n*...and {len(findings) - 10} more. Use the Perf panel for full details.*")
        answer = "\n".join(parts)

    return {
        "answer": answer,
        "sessionId": None,
        "context": {
            "filesUsed": scanned,
            "symbolsUsed": 0,
            "estimatedTokens": 0,
            "budgetUsedPct": 0,
            "truncatedFiles": [],
            "entryPoints": [],
            "graphNodes": 0,
            "bottlenecks": [],
        },
        "durationMs": round(elapsed, 1),
    }


async def _handle_upgrade_intent(request: ChatQueryRequest, t0: float):
    """Handle /upgrade-library command — analyze dependencies."""

    query = request.query.strip()
    tokens = query.split(None, 2)
    library = tokens[1] if len(tokens) > 1 else ""

    workspace = request.workspacePath

    if not library:
        from code4u.interfaces.api.routes.migration import AnalyzeRequest, analyze_dependencies
        result = await analyze_dependencies(AnalyzeRequest(workspacePath=workspace))
        manifests = result.get("manifests", [])
        total = result.get("totalPackages", 0)

        lines = [f"**Dependency Analysis** — Found **{total}** packages:\n"]
        for m in manifests:
            lines.append(f"**{m['file']}** ({m['ecosystem']}):")
            for pkg in m.get("packages", [])[:8]:
                lines.append(f"  - `{pkg['name']}` {pkg.get('currentVersion', '')}")
            if len(m.get("packages", [])) > 8:
                lines.append(f"  - *...and {len(m['packages']) - 8} more*")
            lines.append("")

        answer = "\n".join(lines)
    else:
        from code4u.interfaces.api.routes.migration import MigratePlanRequest, migration_plan
        target = tokens[2] if len(tokens) > 2 else ""
        result = await migration_plan(MigratePlanRequest(
            workspacePath=workspace, library=library, targetVersion=target,
        ))

        risk_icon = {"high": "\U0001f534", "medium": "\U0001f7e0", "low": "\U0001f7e2"}.get(
            result.get("riskLevel", ""), "\u26aa"
        )

        lines = [
            f"**Migration Plan for `{library}`** {risk_icon}\n",
            f"Current: `{result.get('currentVersion', '?')}` \u2192 Target: `{result.get('targetVersion', 'latest')}`",
            f"Risk: **{result.get('riskLevel', '?')}** ({result.get('totalUsages', 0)} usages in {len(result.get('usageFiles', []))} files)\n",
            "**Steps:**",
        ]
        for step in result.get("migrationSteps", []):
            lines.append(f"  {step['step']}. {step['description']}")

        if result.get("usageFiles"):
            lines.append("\n**Affected files:**")
            for uf in result["usageFiles"][:5]:
                lines.append(f"  - `{uf['filePath']}` ({uf['importCount']} import{'s' if uf['importCount'] > 1 else ''})")

        answer = "\n".join(lines)

    elapsed = (time.time() - t0) * 1000

    return {
        "answer": answer,
        "sessionId": None,
        "context": {
            "filesUsed": 0, "symbolsUsed": 0, "estimatedTokens": 0,
            "budgetUsedPct": 0, "truncatedFiles": [], "entryPoints": [],
            "graphNodes": 0, "bottlenecks": [],
        },
        "durationMs": round(elapsed, 1),
    }
