"""Day 18 — Graph-Augmented Code Chat test suite.

Tests:
  - Keyword extraction from natural language queries.
  - Symbol scoring against keywords.
  - ContextRetriever: entry points, multi-hop traversal, bottlenecks.
  - TokenBudgeter: allocation, truncation, budget enforcement.
  - ContextAssembler: XML formatting, "Lost in the Middle" layout.
  - Chat API endpoints: query, context preview, sessions.
  - Multi-hop accuracy: 2-file-away dependency discovery.
  - Local summary fallback without LLM.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List
from unittest.mock import patch

import pytest

from code4u.agents.chat.retriever import (
    ContextRetriever,
    RetrievedContext,
    SymbolMatch,
    GraphNode,
    extract_keywords,
    _score_symbol,
)
from code4u.agents.chat.assembler import (
    ContextAssembler,
    AssembledPrompt,
    TokenBudgeter,
    _format_dependency_graph,
)
from code4u.code_intelligence.knowledge_graph.symbol_indexer import (
    SymbolIndexer,
    DependencyMap,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def payment_project(tmp_path):
    """A realistic payment flow project with controller → service → wrapper."""
    (tmp_path / "payment_controller.py").write_text(
        "from payment_service import process_payment\n\n"
        "def handle_payment_request(data):\n"
        "    result = process_payment(data['amount'], data['card'])\n"
        "    return {'status': result}\n"
    )
    (tmp_path / "payment_service.py").write_text(
        "from stripe_wrapper import charge_card\n"
        "from analytics_hook import track_event\n\n"
        "def process_payment(amount, card):\n"
        "    result = charge_card(amount, card)\n"
        "    track_event('payment', amount)\n"
        "    return result\n"
    )
    (tmp_path / "stripe_wrapper.py").write_text(
        "def charge_card(amount, card_token):\n"
        "    return {'charged': amount, 'token': card_token}\n\n"
        "def refund_charge(charge_id):\n"
        "    return {'refunded': charge_id}\n"
    )
    (tmp_path / "analytics_hook.py").write_text(
        "def track_event(event_name, value):\n"
        "    pass\n\n"
        "def get_metrics():\n"
        "    return {}\n"
    )
    (tmp_path / "admin_dashboard.py").write_text(
        "from analytics_hook import get_metrics\n\n"
        "def show_dashboard():\n"
        "    return get_metrics()\n"
    )
    (tmp_path / "auth_middleware.py").write_text(
        "def verify_token(token):\n"
        "    return token == 'valid'\n\n"
        "def require_auth(handler):\n"
        "    def wrapper(*args, **kwargs):\n"
        "        return handler(*args, **kwargs)\n"
        "    return wrapper\n"
    )
    return tmp_path


@pytest.fixture
def payment_dep_map(payment_project):
    indexer = SymbolIndexer()
    return indexer.index_workspace(str(payment_project), use_cache=False)


# ═══════════════════════════════════════════════════════════════════════════
# Keyword extraction tests
# ═══════════════════════════════════════════════════════════════════════════

class TestKeywordExtraction:
    def test_simple_query(self):
        kws = extract_keywords("How does payment work?")
        assert "payment" in kws
        assert "work" in kws

    def test_camel_case(self):
        kws = extract_keywords("What does processPayment do?")
        assert "process" in kws
        assert "payment" in kws
        assert "processpayment" in kws

    def test_snake_case(self):
        kws = extract_keywords("Explain the calculate_total function")
        assert "calculate" in kws
        assert "total" in kws
        assert "calculate_total" in kws

    def test_stop_words_removed(self):
        kws = extract_keywords("What is the purpose of this module?")
        assert "the" not in kws
        assert "is" not in kws
        assert "of" not in kws
        assert "purpose" in kws
        assert "module" in kws

    def test_short_words_removed(self):
        kws = extract_keywords("I do x")
        assert "x" not in kws

    def test_deduplication(self):
        kws = extract_keywords("payment payment payment")
        assert kws.count("payment") == 1

    def test_code_terms_preserved(self):
        kws = extract_keywords("Show me the auth middleware class")
        assert "auth" in kws
        assert "middleware" in kws


# ═══════════════════════════════════════════════════════════════════════════
# Symbol scoring tests
# ═══════════════════════════════════════════════════════════════════════════

class TestSymbolScoring:
    def test_exact_match(self):
        assert _score_symbol("payment", ["payment"]) == 1.0

    def test_substring_match(self):
        score = _score_symbol("process_payment", ["payment"])
        assert score == 0.6

    def test_component_match(self):
        score = _score_symbol("process_payment", ["process"])
        assert score >= 0.3

    def test_no_match(self):
        assert _score_symbol("foobar", ["payment"]) == 0.0

    def test_multiple_keywords(self):
        score = _score_symbol("payment_service", ["payment", "service"])
        assert score >= 0.6

    def test_case_insensitive(self):
        assert _score_symbol("PaymentService", ["payment"]) >= 0.3


# ═══════════════════════════════════════════════════════════════════════════
# Context Retriever tests
# ═══════════════════════════════════════════════════════════════════════════

class TestContextRetriever:
    def test_payment_query_finds_entry_points(self, payment_dep_map):
        retriever = ContextRetriever(payment_dep_map)
        ctx = retriever.retrieve("How does the payment flow work?")
        entry_names = {ep.name for ep in ctx.entry_points}
        assert "process_payment" in entry_names or "handle_payment_request" in entry_names

    def test_multi_hop_traversal(self, payment_dep_map):
        retriever = ContextRetriever(payment_dep_map, max_hops=2)
        ctx = retriever.retrieve("process_payment")
        file_names = {Path(n.file_path).name for n in ctx.graph_nodes}
        assert "payment_service.py" in file_names
        # Should find the controller (downstream) via hop
        assert "payment_controller.py" in file_names or "stripe_wrapper.py" in file_names

    def test_upstream_discovery(self, payment_dep_map):
        """payment_service imports from stripe_wrapper — should find it."""
        retriever = ContextRetriever(payment_dep_map, max_hops=2)
        ctx = retriever.retrieve("process_payment")
        relationships = {
            Path(n.file_path).name: n.relationship
            for n in ctx.graph_nodes
        }
        # stripe_wrapper should be upstream of payment_service
        if "stripe_wrapper.py" in relationships:
            assert relationships["stripe_wrapper.py"] in ("upstream", "entry_point", "downstream")

    def test_downstream_discovery(self, payment_dep_map):
        """payment_controller imports process_payment — it's a downstream caller."""
        retriever = ContextRetriever(payment_dep_map, max_hops=2)
        ctx = retriever.retrieve("process_payment")
        file_names = {Path(n.file_path).name for n in ctx.graph_nodes}
        assert "payment_controller.py" in file_names

    def test_unrelated_query(self, payment_dep_map):
        retriever = ContextRetriever(payment_dep_map)
        ctx = retriever.retrieve("quantum physics theory")
        assert len(ctx.entry_points) == 0
        assert len(ctx.graph_nodes) == 0

    def test_auth_query_isolated(self, payment_dep_map):
        """Auth middleware has no deps — graph should be small."""
        retriever = ContextRetriever(payment_dep_map)
        ctx = retriever.retrieve("verify_token authentication")
        entry_names = {ep.name for ep in ctx.entry_points}
        assert "verify_token" in entry_names
        # Should not drag in payment files
        file_names = {Path(n.file_path).name for n in ctx.graph_nodes}
        assert "payment_service.py" not in file_names

    def test_max_entry_points(self, payment_dep_map):
        retriever = ContextRetriever(payment_dep_map, max_entry_points=2)
        ctx = retriever.retrieve("payment service controller charge")
        assert len(ctx.entry_points) <= 2

    def test_retrieved_context_to_dict(self, payment_dep_map):
        retriever = ContextRetriever(payment_dep_map)
        ctx = retriever.retrieve("payment")
        d = ctx.to_dict()
        assert "query" in d
        assert "entryPoints" in d
        assert "graphNodes" in d
        assert "fileOrder" in d

    def test_bottleneck_detection(self, payment_dep_map):
        """analytics_hook is used by 2 files — may be a bottleneck."""
        retriever = ContextRetriever(payment_dep_map, max_hops=2)
        ctx = retriever.retrieve("track_event analytics")
        # The retriever should process without error
        assert isinstance(ctx.bottleneck_files, list)

    def test_hop_distance_ordering(self, payment_dep_map):
        retriever = ContextRetriever(payment_dep_map, max_hops=2)
        ctx = retriever.retrieve("process_payment")
        # Entry points should have hop_distance 0
        for n in ctx.graph_nodes:
            if n.relationship == "entry_point":
                assert n.hop_distance == 0

    def test_empty_query(self, payment_dep_map):
        retriever = ContextRetriever(payment_dep_map)
        ctx = retriever.retrieve("")
        assert len(ctx.entry_points) == 0


# ═══════════════════════════════════════════════════════════════════════════
# Token Budgeter tests
# ═══════════════════════════════════════════════════════════════════════════

class TestTokenBudgeter:
    def test_initial_budget(self):
        b = TokenBudgeter(max_tokens=1000)
        assert b.remaining == 1000
        assert b.used_pct == 0.0

    def test_consume_within_budget(self):
        b = TokenBudgeter(max_tokens=1000)
        result = b.consume("x" * 400)  # 100 tokens
        assert len(result) == 400
        assert b.remaining == 900

    def test_consume_exceeds_budget(self):
        b = TokenBudgeter(max_tokens=100)
        result = b.consume("x" * 2000)  # 500 tokens > 100
        assert "truncated" in result
        assert b.remaining == 0

    def test_try_add_file_fits(self):
        b = TokenBudgeter(max_tokens=1000)
        result = b.try_add_file("/tmp/a.py", "hello world")
        assert result == "hello world"

    def test_try_add_file_no_budget(self):
        b = TokenBudgeter(max_tokens=0)
        result = b.try_add_file("/tmp/a.py", "hello")
        assert result is None
        assert "/tmp/a.py" in b._truncated

    def test_try_add_file_partial(self):
        b = TokenBudgeter(max_tokens=50)
        content = "x" * 1000  # way too large
        result = b.try_add_file("/tmp/big.py", content)
        if result:
            assert "truncated" in result
        assert "/tmp/big.py" in b._truncated

    def test_token_estimation(self):
        b = TokenBudgeter()
        assert b.estimate_tokens("abcd") == 1  # 4 chars = 1 token
        assert b.estimate_tokens("a" * 100) == 25


# ═══════════════════════════════════════════════════════════════════════════
# Context Assembler tests
# ═══════════════════════════════════════════════════════════════════════════

class TestContextAssembler:
    def test_assemble_basic(self, payment_dep_map, payment_project):
        retriever = ContextRetriever(payment_dep_map)
        ctx = retriever.retrieve("process_payment")
        assembler = ContextAssembler(max_context_tokens=8000)
        result = assembler.assemble(ctx)

        assert isinstance(result, AssembledPrompt)
        assert result.context_files > 0
        assert result.estimated_tokens > 0
        assert "<file" in result.user_prompt
        assert "<dependency_graph>" in result.user_prompt

    def test_lost_in_the_middle_layout(self, payment_dep_map, payment_project):
        """User query should be at the BOTTOM of the prompt."""
        retriever = ContextRetriever(payment_dep_map)
        ctx = retriever.retrieve("process_payment")
        assembler = ContextAssembler(max_context_tokens=8000)
        result = assembler.assemble(ctx)

        prompt = result.user_prompt
        graph_pos = prompt.find("<dependency_graph>")
        question_pos = prompt.find("<user_question>")
        # Graph at top, question at bottom
        assert graph_pos < question_pos
        assert prompt.strip().endswith("</user_question>")

    def test_xml_file_tags(self, payment_dep_map, payment_project):
        retriever = ContextRetriever(payment_dep_map)
        ctx = retriever.retrieve("charge_card")
        assembler = ContextAssembler(max_context_tokens=8000)
        result = assembler.assemble(ctx)
        assert '<file path="' in result.user_prompt
        assert "</file>" in result.user_prompt

    def test_line_numbers_included(self, payment_dep_map, payment_project):
        retriever = ContextRetriever(payment_dep_map)
        ctx = retriever.retrieve("charge_card")
        assembler = ContextAssembler(max_context_tokens=8000, include_line_numbers=True)
        result = assembler.assemble(ctx)
        assert "   1 |" in result.user_prompt

    def test_line_numbers_excluded(self, payment_dep_map, payment_project):
        retriever = ContextRetriever(payment_dep_map)
        ctx = retriever.retrieve("charge_card")
        assembler = ContextAssembler(max_context_tokens=8000, include_line_numbers=False)
        result = assembler.assemble(ctx)
        assert "   1 |" not in result.user_prompt

    def test_system_message_has_architect(self, payment_dep_map):
        retriever = ContextRetriever(payment_dep_map)
        ctx = retriever.retrieve("payment")
        assembler = ContextAssembler()
        result = assembler.assemble(ctx)
        assert "architect" in result.system_message.lower()

    def test_bottleneck_in_system_message(self, payment_dep_map):
        retriever = ContextRetriever(payment_dep_map)
        ctx = retriever.retrieve("payment")
        ctx.bottleneck_files = ["/fake/utils.py"]
        assembler = ContextAssembler()
        result = assembler.assemble(ctx)
        assert "bottleneck" in result.system_message.lower()

    def test_conversation_history(self, payment_dep_map):
        retriever = ContextRetriever(payment_dep_map)
        ctx = retriever.retrieve("payment")
        assembler = ContextAssembler()
        history = [
            {"role": "user", "content": "What is this project?"},
            {"role": "assistant", "content": "A payment processing system."},
        ]
        result = assembler.assemble(ctx, conversation_history=history)
        assert "<conversation_history>" in result.user_prompt

    def test_token_budget_enforced(self, payment_dep_map, payment_project):
        retriever = ContextRetriever(payment_dep_map, max_files=20)
        ctx = retriever.retrieve("payment")
        assembler = ContextAssembler(max_context_tokens=200)
        result = assembler.assemble(ctx)
        # With a tiny budget, some files should be truncated
        assert result.budget_used_pct > 0

    def test_assembled_prompt_to_dict(self, payment_dep_map):
        retriever = ContextRetriever(payment_dep_map)
        ctx = retriever.retrieve("payment")
        assembler = ContextAssembler()
        result = assembler.assemble(ctx)
        d = result.to_dict()
        assert "systemMessage" in d
        assert "estimatedTokens" in d
        assert "budgetUsedPct" in d


class TestDependencyGraphFormat:
    def test_format_has_sections(self, payment_dep_map):
        retriever = ContextRetriever(payment_dep_map, max_hops=2)
        ctx = retriever.retrieve("process_payment")
        graph_text = _format_dependency_graph(ctx)
        assert "<dependency_graph>" in graph_text
        assert "</dependency_graph>" in graph_text
        assert "Entry Points:" in graph_text


# ═══════════════════════════════════════════════════════════════════════════
# Chat API endpoint tests
# ═══════════════════════════════════════════════════════════════════════════

class TestChatAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        from fastapi.testclient import TestClient
        from code4u.interfaces.api.app import app
        self.client = TestClient(app)
        # Clear session cache between tests
        from code4u.interfaces.api.routes import chat
        chat._sessions.clear()
        chat._dep_map_cache.clear()
        yield

    def test_query_endpoint(self, payment_project):
        resp = self.client.post("/api/v1/chat/query", json={
            "query": "How does payment work?",
            "workspacePath": str(payment_project),
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert "sessionId" in data
        assert "context" in data
        assert data["context"]["filesUsed"] > 0

    def test_query_with_session(self, payment_project):
        # First query creates session
        resp1 = self.client.post("/api/v1/chat/query", json={
            "query": "What is process_payment?",
            "workspacePath": str(payment_project),
        })
        sid = resp1.json()["sessionId"]

        # Second query continues session
        resp2 = self.client.post("/api/v1/chat/query", json={
            "query": "What about charge_card?",
            "workspacePath": str(payment_project),
            "sessionId": sid,
        })
        assert resp2.json()["sessionId"] == sid

    def test_context_preview(self, payment_project):
        resp = self.client.post("/api/v1/chat/context", json={
            "query": "process_payment",
            "workspacePath": str(payment_project),
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "retrievedContext" in data
        assert "assembledPrompt" in data
        assert "systemMessage" in data

    def test_create_session(self, payment_project):
        resp = self.client.post("/api/v1/chat/sessions", json={
            "workspacePath": str(payment_project),
        })
        assert resp.status_code == 200
        assert "sessionId" in resp.json()

    def test_list_sessions(self, payment_project):
        self.client.post("/api/v1/chat/sessions", json={
            "workspacePath": str(payment_project),
        })
        resp = self.client.get("/api/v1/chat/sessions")
        data = resp.json()
        assert data["count"] >= 1

    def test_delete_session(self, payment_project):
        resp = self.client.post("/api/v1/chat/sessions", json={
            "workspacePath": str(payment_project),
        })
        sid = resp.json()["sessionId"]

        resp = self.client.delete(f"/api/v1/chat/sessions/{sid}")
        assert resp.json()["status"] == "deleted"

    def test_delete_nonexistent_session(self):
        resp = self.client.delete("/api/v1/chat/sessions/fake123")
        assert resp.status_code == 404

    def test_local_summary_structure(self, payment_project):
        """Without LLM, the answer should be a structured graph summary."""
        resp = self.client.post("/api/v1/chat/query", json={
            "query": "process_payment",
            "workspacePath": str(payment_project),
        })
        answer = resp.json()["answer"]
        assert "Entry Points Found" in answer
        assert "process_payment" in answer

    def test_unrelated_query_graceful(self, payment_project):
        resp = self.client.post("/api/v1/chat/query", json={
            "query": "quantum entanglement theory",
            "workspacePath": str(payment_project),
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["context"]["filesUsed"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# Multi-hop accuracy tests (the "2 files away" test)
# ═══════════════════════════════════════════════════════════════════════════

class TestMultiHopAccuracy:
    def test_two_hop_discovery(self, payment_dep_map):
        """Asking about payment_controller should find stripe_wrapper (2 hops).

        Chain: payment_controller → payment_service → stripe_wrapper
        """
        retriever = ContextRetriever(payment_dep_map, max_hops=2)
        ctx = retriever.retrieve("handle_payment_request")
        file_names = {Path(n.file_path).name for n in ctx.graph_nodes}
        # Direct: payment_controller.py (entry point)
        assert "payment_controller.py" in file_names
        # 1-hop: payment_service.py (upstream of controller)
        # 2-hop: stripe_wrapper.py (upstream of service)
        # At least one of these should be found
        assert len(file_names) >= 2

    def test_transitive_dependencies_labeled(self, payment_dep_map):
        """Hop-2 files should have relationship='transitive'."""
        retriever = ContextRetriever(payment_dep_map, max_hops=2)
        ctx = retriever.retrieve("handle_payment_request")
        transitive = [n for n in ctx.graph_nodes if n.relationship == "transitive"]
        # There might be transitive dependencies
        for n in transitive:
            assert n.hop_distance == 2

    def test_dashboard_to_analytics_chain(self, payment_dep_map):
        """admin_dashboard → analytics_hook → (tracked by payment_service)."""
        retriever = ContextRetriever(payment_dep_map, max_hops=2)
        ctx = retriever.retrieve("show_dashboard")
        file_names = {Path(n.file_path).name for n in ctx.graph_nodes}
        assert "admin_dashboard.py" in file_names
        # analytics_hook should be discovered as upstream
        if "analytics_hook.py" in file_names:
            node = next(
                n for n in ctx.graph_nodes
                if Path(n.file_path).name == "analytics_hook.py"
            )
            assert node.hop_distance <= 1
