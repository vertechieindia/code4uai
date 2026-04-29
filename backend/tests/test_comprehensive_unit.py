"""Comprehensive Unit Tests (White Box Testing) for code4u.ai backend.

Covers isolated component behavior: config, ChiefArchitect, SmartRouter,
TFIDFEmbedder, LocalVectorStore, air-gap guards, DistillationStore,
and CollaborationDocument CRDT operations.
"""

from __future__ import annotations

import os
import pytest

# ---------------------------------------------------------------------------
# Settings / Config
# ---------------------------------------------------------------------------


def test_settings_default_app_name():
    """Settings defaults: app_name is code4u.ai."""
    from code4u.core.config import Settings
    s = Settings()
    assert s.app_name == "code4u.ai"


def test_settings_default_environment():
    """Settings defaults: environment is development."""
    from code4u.core.config import Settings
    s = Settings()
    assert s.environment == "development"


def test_settings_default_port():
    """Settings defaults: port is 8000."""
    from code4u.core.config import Settings
    s = Settings()
    assert s.port == 8000


def test_settings_default_air_gapped_mode():
    """Settings defaults: air_gapped_mode is False."""
    from code4u.core.config import Settings
    s = Settings()
    assert s.air_gapped_mode is False


def test_settings_default_ollama_base_url():
    """Settings defaults: ollama_base_url points to localhost."""
    from code4u.core.config import Settings
    s = Settings()
    assert "localhost" in s.ollama_base_url


def test_get_settings_returns_singleton():
    """get_settings() returns cached Settings instance."""
    from code4u.core.config import get_settings
    a = get_settings()
    b = get_settings()
    assert a is b


def test_settings_extra_ignored():
    """Settings ignores extra env vars (extra='ignore')."""
    from code4u.core.config import Settings
    s = Settings()
    assert hasattr(s, "app_name")
    # Unknown fields should not raise
    assert s.app_name == "code4u.ai"


# ---------------------------------------------------------------------------
# ChiefArchitect.estimate_complexity()
# ---------------------------------------------------------------------------


def test_chief_estimate_complexity_low_rename():
    """ChiefArchitect.estimate_complexity returns 'low' for simple rename."""
    from code4u.agents.orchestrator.chief import ChiefArchitect
    chief = ChiefArchitect()
    assert chief.estimate_complexity("rename variable x to y") == "low"


def test_chief_estimate_complexity_low_lint():
    """ChiefArchitect.estimate_complexity returns 'low' for lint tasks."""
    from code4u.agents.orchestrator.chief import ChiefArchitect
    chief = ChiefArchitect()
    assert chief.estimate_complexity("fix unused import") == "low"


def test_chief_estimate_complexity_medium_single_high_signal():
    """ChiefArchitect.estimate_complexity returns 'medium' for one high signal."""
    from code4u.agents.orchestrator.chief import ChiefArchitect
    chief = ChiefArchitect()
    assert chief.estimate_complexity("refactor the auth module") == "medium"


def test_chief_estimate_complexity_high_multiple_signals():
    """ChiefArchitect.estimate_complexity returns 'high' for multiple high signals."""
    from code4u.agents.orchestrator.chief import ChiefArchitect
    chief = ChiefArchitect()
    result = chief.estimate_complexity(
        "refactor and restructure the entire authentication module across all files"
    )
    assert result == "high"


def test_chief_estimate_complexity_high_long_goal():
    """ChiefArchitect.estimate_complexity returns 'high' for very long goals."""
    from code4u.agents.orchestrator.chief import ChiefArchitect
    chief = ChiefArchitect()
    long_goal = "x" * 250
    assert chief.estimate_complexity(long_goal) == "high"


def test_chief_estimate_complexity_low_short():
    """ChiefArchitect.estimate_complexity returns 'low' for short neutral goals."""
    from code4u.agents.orchestrator.chief import ChiefArchitect
    chief = ChiefArchitect()
    assert chief.estimate_complexity("add docstring") == "low"


# ---------------------------------------------------------------------------
# SmartRouter MODEL_ROUTING_TABLE
# ---------------------------------------------------------------------------


def test_model_routing_table_has_required_agents():
    """MODEL_ROUTING_TABLE contains expected agent types."""
    from code4u.ai_engine.llm.smart_router import MODEL_ROUTING_TABLE
    required = {"index", "graph", "vision", "migration", "heal", "refactor", "chief", "chat"}
    for agent in required:
        assert agent in MODEL_ROUTING_TABLE


def test_model_routing_table_entries_have_cloud_and_local():
    """Each MODEL_ROUTING_TABLE entry has cloud and local keys."""
    from code4u.ai_engine.llm.smart_router import MODEL_ROUTING_TABLE
    for agent, entry in MODEL_ROUTING_TABLE.items():
        assert "cloud" in entry
        assert "local" in entry
        assert isinstance(entry["cloud"], str)
        assert isinstance(entry["local"], str)


def test_get_model_for_agent_cloud_returns_cloud_model():
    """get_model_for_agent(air_gapped=False) returns cloud model."""
    from code4u.ai_engine.llm.smart_router import get_model_for_agent, MODEL_ROUTING_TABLE
    for agent in ["heal", "refactor", "chief"]:
        model = get_model_for_agent(agent, air_gapped=False)
        expected = MODEL_ROUTING_TABLE[agent]["cloud"]
        assert model == expected


def test_get_model_for_agent_air_gapped_returns_local_model():
    """get_model_for_agent(air_gapped=True) returns local model."""
    from code4u.ai_engine.llm.smart_router import get_model_for_agent, MODEL_ROUTING_TABLE
    for agent in ["heal", "refactor", "chief"]:
        model = get_model_for_agent(agent, air_gapped=True)
        expected = MODEL_ROUTING_TABLE[agent]["local"]
        assert model == expected


def test_get_model_for_agent_unknown_falls_back_to_chat():
    """get_model_for_agent for unknown agent falls back to chat entry."""
    from code4u.ai_engine.llm.smart_router import get_model_for_agent
    model = get_model_for_agent("unknown_agent_xyz", air_gapped=False)
    assert isinstance(model, str)
    assert len(model) > 0


# ---------------------------------------------------------------------------
# classify_complexity
# ---------------------------------------------------------------------------


def test_classify_complexity_cheap_rename():
    """classify_complexity returns 'cheap' for rename patterns."""
    from code4u.ai_engine.llm.smart_router import classify_complexity
    assert classify_complexity("rename foo to bar") == "cheap"


def test_classify_complexity_premium_multi_file():
    """classify_complexity returns 'premium' for 3+ file_count."""
    from code4u.ai_engine.llm.smart_router import classify_complexity
    assert classify_complexity("anything", file_count=3) == "premium"


def test_classify_complexity_premium_refactor():
    """classify_complexity returns 'premium' for refactor patterns."""
    from code4u.ai_engine.llm.smart_router import classify_complexity
    assert classify_complexity("refactor the module for better structure") == "premium"


# ---------------------------------------------------------------------------
# TFIDFEmbedder
# ---------------------------------------------------------------------------


def test_tfidf_embedder_produces_fixed_dimension():
    """TFIDFEmbedder.embed returns vector of configured dimension."""
    from code4u.ai_engine.vector_store import TFIDFEmbedder
    emb = TFIDFEmbedder(dim=256)
    vec = emb.embed("hello world")
    assert len(vec) == 256


def test_tfidf_embedder_deterministic():
    """TFIDFEmbedder.embed is deterministic for same input."""
    from code4u.ai_engine.vector_store import TFIDFEmbedder
    emb = TFIDFEmbedder(dim=128)
    a = emb.embed("def foo(): pass")
    b = emb.embed("def foo(): pass")
    assert a == b


def test_tfidf_embedder_empty_returns_zero_vec():
    """TFIDFEmbedder.embed returns zero vector for empty/stopword-only text."""
    from code4u.ai_engine.vector_store import TFIDFEmbedder
    emb = TFIDFEmbedder(dim=64)
    vec = emb.embed("")
    assert len(vec) == 64
    assert all(v == 0.0 for v in vec)


def test_tfidf_embed_batch():
    """TFIDFEmbedder.embed_batch returns list of embeddings."""
    from code4u.ai_engine.vector_store import TFIDFEmbedder
    emb = TFIDFEmbedder(dim=64)
    texts = ["hello", "world", "code"]
    batch = emb.embed_batch(texts)
    assert len(batch) == 3
    assert all(len(v) == 64 for v in batch)


# ---------------------------------------------------------------------------
# LocalVectorStore
# ---------------------------------------------------------------------------


def test_local_vector_store_add_and_count():
    """LocalVectorStore add_documents increases count."""
    from code4u.ai_engine.vector_store import LocalVectorStore, VectorDocument
    store = LocalVectorStore(dim=64)
    store.add_documents([
        VectorDocument(id="d1", content="def hello(): pass"),
        VectorDocument(id="d2", content="class Foo: pass"),
    ])
    assert store.count == 2


def test_local_vector_store_search_returns_sorted_by_score():
    """LocalVectorStore.search returns results sorted by score descending."""
    from code4u.ai_engine.vector_store import LocalVectorStore, VectorDocument
    store = LocalVectorStore(dim=64)
    store.add_documents([
        VectorDocument(id="a", content="authentication login password"),
        VectorDocument(id="b", content="unrelated xyz"),
    ])
    results = store.search("authentication login", top_k=5)
    assert len(results) >= 1
    for i in range(len(results) - 1):
        assert results[i].score >= results[i + 1].score


def test_local_vector_store_remove():
    """LocalVectorStore.remove deletes document by id."""
    from code4u.ai_engine.vector_store import LocalVectorStore, VectorDocument
    store = LocalVectorStore(dim=64)
    store.add_documents([VectorDocument(id="x", content="test")])
    assert store.count == 1
    removed = store.remove("x")
    assert removed is True
    assert store.count == 0


def test_local_vector_store_clear():
    """LocalVectorStore.clear empties the store."""
    from code4u.ai_engine.vector_store import LocalVectorStore, VectorDocument
    store = LocalVectorStore(dim=64)
    store.add_documents([VectorDocument(id="x", content="test")])
    store.clear()
    assert store.count == 0
    assert store.search("test", top_k=5) == []


def test_local_vector_store_stats():
    """LocalVectorStore.stats returns expected keys."""
    from code4u.ai_engine.vector_store import LocalVectorStore
    store = LocalVectorStore(dim=64)
    stats = store.stats()
    assert "documentCount" in stats
    assert "dimension" in stats
    assert "backend" in stats


# ---------------------------------------------------------------------------
# Air-gapped guards
# ---------------------------------------------------------------------------


def test_guard_external_call_allows_local_when_air_gapped():
    """guard_external_call allows 'local' provider when air-gapped."""
    from code4u.interfaces.api.routes.airgap import set_air_gapped, guard_external_call
    set_air_gapped(True)
    try:
        guard_external_call("local", "")
    except RuntimeError:
        pytest.fail("local provider should be allowed when air-gapped")
    finally:
        set_air_gapped(False)


def test_guard_external_call_blocks_openai_when_air_gapped():
    """guard_external_call blocks OpenAI when air-gapped."""
    from code4u.interfaces.api.routes.airgap import set_air_gapped, guard_external_call
    set_air_gapped(True)
    try:
        with pytest.raises(RuntimeError) as exc_info:
            guard_external_call("openai", "https://api.openai.com/v1/chat")
        assert "blocked" in str(exc_info.value).lower() or "openai" in str(exc_info.value).lower()
    finally:
        set_air_gapped(False)


def test_guard_external_call_passes_when_not_air_gapped():
    """guard_external_call does nothing when not air-gapped."""
    from code4u.interfaces.api.routes.airgap import set_air_gapped, guard_external_call
    set_air_gapped(False)
    guard_external_call("openai", "https://api.openai.com/v1/chat")


def test_blocked_domains_contains_expected():
    """BLOCKED_DOMAINS contains major cloud API domains."""
    from code4u.interfaces.api.routes.airgap import BLOCKED_DOMAINS
    assert "api.openai.com" in BLOCKED_DOMAINS
    assert "api.anthropic.com" in BLOCKED_DOMAINS


# ---------------------------------------------------------------------------
# DistillationStore
# ---------------------------------------------------------------------------


def test_distillation_store_add_increments_count():
    """DistillationStore.add increments count."""
    from code4u.ai_engine.distillation import DistillationStore, TrainingExample
    store = DistillationStore()
    store.add(TrainingExample(goal="test", user_input="x", assistant_output="y"))
    assert store.count >= 1


def test_distillation_store_stats_structure():
    """DistillationStore.stats returns expected structure."""
    from code4u.ai_engine.distillation import DistillationStore, TrainingExample
    store = DistillationStore()
    store.add(TrainingExample(goal="g", user_input="u", assistant_output="a", agent_type="heal"))
    stats = store.stats()
    assert "totalExamples" in stats
    assert "byAgent" in stats
    assert "byModel" in stats
    assert "byComplexity" in stats


def test_distillation_store_export_jsonl_creates_file():
    """DistillationStore.export_jsonl creates a file on disk."""
    import tempfile
    from code4u.ai_engine.distillation import DistillationStore, TrainingExample
    store = DistillationStore()
    store.add(TrainingExample(goal="g", user_input="u", assistant_output="a"))
    with tempfile.TemporaryDirectory() as tmp:
        path = store.export_jsonl(path=os.path.join(tmp, "out.jsonl"))
        assert os.path.exists(path)
        with open(path) as f:
            lines = f.readlines()
        assert len(lines) >= 1


def test_distillation_store_clear():
    """DistillationStore.clear empties examples."""
    from code4u.ai_engine.distillation import DistillationStore, TrainingExample
    store = DistillationStore()
    store.add(TrainingExample(goal="g", user_input="u", assistant_output="a"))
    store.clear()
    assert store.count == 0


# ---------------------------------------------------------------------------
# CollaborationDocument CRDT
# ---------------------------------------------------------------------------


def test_collaboration_document_insert():
    """CollaborationDocument apply_operation INSERT appends text."""
    from code4u.core.collaboration import CollaborationDocument, Operation, OpType
    doc = CollaborationDocument("test.py", "hello")
    doc.apply_operation(Operation(type=OpType.INSERT, offset=5, text=" world"))
    assert doc.content == "hello world"


def test_collaboration_document_delete():
    """CollaborationDocument apply_operation DELETE removes text."""
    from code4u.core.collaboration import CollaborationDocument, Operation, OpType
    doc = CollaborationDocument("test.py", "hello world")
    doc.apply_operation(Operation(type=OpType.DELETE, offset=5, length=6))
    assert doc.content == "hello"


def test_collaboration_document_replace():
    """CollaborationDocument apply_operation REPLACE replaces text."""
    from code4u.core.collaboration import CollaborationDocument, Operation, OpType
    doc = CollaborationDocument("test.py", "hello world")
    doc.apply_operation(Operation(type=OpType.REPLACE, offset=6, length=5, text="code4u"))
    assert doc.content == "hello code4u"


def test_collaboration_document_join_leave():
    """CollaborationDocument join/leave updates participant count."""
    from code4u.core.collaboration import CollaborationDocument, ParticipantType
    doc = CollaborationDocument("test.py", "")
    p = doc.join("user1", "Alice", ParticipantType.HUMAN)
    assert doc.participant_count == 1
    assert p.color
    doc.leave("user1")
    assert doc.participant_count == 0


def test_collaboration_document_operations_logged():
    """CollaborationDocument records operations for sync."""
    from code4u.core.collaboration import CollaborationDocument, Operation, OpType
    doc = CollaborationDocument("test.py", "x")
    doc.apply_operation(Operation(type=OpType.INSERT, offset=1, text="y"))
    ops = doc.get_operations(since_lamport=0)
    assert len(ops) >= 1
    assert ops[0].get("type") == "insert"
