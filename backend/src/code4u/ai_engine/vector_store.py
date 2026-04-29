"""Local vector store with FAISS fallback.

When a cloud vector database (Qdrant, Pinecone, Weaviate) is unavailable
or the platform is running in air-gapped mode, this module provides an
in-process alternative backed by numpy + a simple flat-IP index.

If ``faiss-cpu`` is installed it will be used; otherwise a pure-numpy
brute-force cosine search is used (sufficient for <100 k documents).
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import threading
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger("vector_store")

# ---------------------------------------------------------------------------
# Try to import FAISS — gracefully fall back to numpy
# ---------------------------------------------------------------------------

_HAS_FAISS = False
_HAS_NUMPY = False

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    np = None  # type: ignore[assignment]

try:
    import faiss  # type: ignore[import-untyped]
    _HAS_FAISS = True
except ImportError:
    faiss = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class VectorDocument:
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None


@dataclass
class SearchResult:
    id: str
    score: float
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Lightweight TF-IDF embedder (no external model needed)
# ---------------------------------------------------------------------------

_STOPWORDS = frozenset(
    "the a an is are was were be been being have has had do does did "
    "will would shall should may might can could of in to for on with "
    "at by from as into through during before after above below between "
    "and or but not no nor so yet both either neither each every all "
    "any few more most other some such than too very it its this that "
    "these those i me my we our you your he him his she her they them "
    "their what which who whom how when where why if then else".split()
)


def _tokenize(text: str) -> List[str]:
    text = re.sub(r"[A-Z]", lambda m: " " + m.group().lower(), text)
    text = re.sub(r"[_\-./\\]", " ", text)
    text = re.sub(r"[^a-z0-9\s]", "", text.lower())
    return [t for t in text.split() if len(t) > 1 and t not in _STOPWORDS]


class TFIDFEmbedder:
    """Produces fixed-dimension dense vectors from text using hashed TF-IDF.

    Uses feature hashing to avoid storing a vocabulary mapping while still
    producing deterministic embeddings. Dimension defaults to 256.
    """

    def __init__(self, dim: int = 256):
        self._dim = dim

    def embed(self, text: str) -> List[float]:
        tokens = _tokenize(text)
        vec = [0.0] * self._dim
        if not tokens:
            return vec
        tf = Counter(tokens)
        total = len(tokens)
        for token, count in tf.items():
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            idx = h % self._dim
            sign = 1.0 if (h // self._dim) % 2 == 0 else -1.0
            tfidf = (count / total) * (1.0 + math.log(max(total / (count + 1), 1)))
            vec[idx] += sign * tfidf
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed(t) for t in texts]


# ---------------------------------------------------------------------------
# Local Vector Store
# ---------------------------------------------------------------------------

class LocalVectorStore:
    """In-process vector store with optional FAISS acceleration.

    Usage::

        store = LocalVectorStore()
        store.add_documents([
            VectorDocument(id="f1", content="def hello(): ..."),
            VectorDocument(id="f2", content="class Foo: ..."),
        ])
        results = store.search("greeting function", top_k=5)
    """

    def __init__(self, dim: int = 256):
        self._dim = dim
        self._embedder = TFIDFEmbedder(dim)
        self._docs: Dict[str, VectorDocument] = {}
        self._index: Optional[Any] = None  # faiss.IndexFlatIP or None
        self._id_list: List[str] = []
        self._lock = threading.Lock()
        self._dirty = True
        logger.info(
            "local_vector_store_init",
            backend="faiss" if _HAS_FAISS else ("numpy" if _HAS_NUMPY else "python"),
            dim=dim,
        )

    @property
    def count(self) -> int:
        return len(self._docs)

    def add_documents(self, docs: List[VectorDocument]) -> int:
        """Add or update documents. Returns number added."""
        added = 0
        with self._lock:
            for doc in docs:
                if doc.embedding is None:
                    doc.embedding = self._embedder.embed(doc.content)
                self._docs[doc.id] = doc
                added += 1
            self._dirty = True
        return added

    def remove(self, doc_id: str) -> bool:
        with self._lock:
            if doc_id in self._docs:
                del self._docs[doc_id]
                self._dirty = True
                return True
            return False

    def _rebuild_index(self) -> None:
        """Rebuild the FAISS / numpy index from current documents."""
        self._id_list = list(self._docs.keys())
        if not self._id_list:
            self._index = None
            self._dirty = False
            return

        if _HAS_FAISS and _HAS_NUMPY:
            vectors = np.array(
                [self._docs[did].embedding for did in self._id_list],
                dtype=np.float32,
            )
            index = faiss.IndexFlatIP(self._dim)
            index.add(vectors)  # type: ignore[arg-type]
            self._index = index
        elif _HAS_NUMPY:
            self._index = np.array(
                [self._docs[did].embedding for did in self._id_list],
                dtype=np.float32,
            )
        else:
            self._index = [self._docs[did].embedding for did in self._id_list]

        self._dirty = False

    def search(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """Semantic search using cosine similarity."""
        with self._lock:
            if self._dirty:
                self._rebuild_index()

            if not self._id_list:
                return []

            q_vec = self._embedder.embed(query)

            if _HAS_FAISS and _HAS_NUMPY and isinstance(self._index, faiss.Index):
                q_np = np.array([q_vec], dtype=np.float32)
                k = min(top_k, len(self._id_list))
                distances, indices = self._index.search(q_np, k)
                results = []
                for dist, idx in zip(distances[0], indices[0]):
                    if idx < 0:
                        continue
                    did = self._id_list[idx]
                    doc = self._docs[did]
                    results.append(SearchResult(
                        id=did,
                        score=float(dist),
                        content=doc.content[:500],
                        metadata=doc.metadata,
                    ))
                return results

            if _HAS_NUMPY and isinstance(self._index, np.ndarray):
                q_np = np.array(q_vec, dtype=np.float32)
                scores = self._index @ q_np
                top_indices = scores.argsort()[::-1][:top_k]
                return [
                    SearchResult(
                        id=self._id_list[i],
                        score=float(scores[i]),
                        content=self._docs[self._id_list[i]].content[:500],
                        metadata=self._docs[self._id_list[i]].metadata,
                    )
                    for i in top_indices
                    if scores[i] > 0.01
                ]

            scored: List[Tuple[float, int]] = []
            for i, emb in enumerate(self._index):  # type: ignore[union-attr]
                dot = sum(a * b for a, b in zip(q_vec, emb))
                if dot > 0.01:
                    scored.append((dot, i))
            scored.sort(reverse=True)
            return [
                SearchResult(
                    id=self._id_list[idx],
                    score=score,
                    content=self._docs[self._id_list[idx]].content[:500],
                    metadata=self._docs[self._id_list[idx]].metadata,
                )
                for score, idx in scored[:top_k]
            ]

    def clear(self) -> None:
        with self._lock:
            self._docs.clear()
            self._id_list.clear()
            self._index = None
            self._dirty = True

    def stats(self) -> Dict[str, Any]:
        return {
            "documentCount": self.count,
            "dimension": self._dim,
            "backend": "faiss" if (_HAS_FAISS and _HAS_NUMPY) else ("numpy" if _HAS_NUMPY else "python"),
            "hasFaiss": _HAS_FAISS,
            "hasNumpy": _HAS_NUMPY,
        }


# ---------------------------------------------------------------------------
# Partitioned (Multi-Tenant) Vector Store
# ---------------------------------------------------------------------------

class PartitionedVectorStore:
    """Multi-tenant vector store with per-project indexes + global wisdom index.
    
    Each project gets its own fast local index for project-specific searches.
    A separate 'global' index stores cross-project Wisdom Nuggets for
    organization-wide semantic search.
    
    This architecture ensures:
      - Sub-millisecond project-scoped searches (small index per tenant)
      - Fast cross-project wisdom queries (dedicated wisdom index)
      - Memory isolation between tenants
    """

    def __init__(self, dim: int = 256) -> None:
        self._dim = dim
        self._partitions: Dict[str, LocalVectorStore] = {}
        self._global_wisdom = LocalVectorStore(dim)
        self._lock = threading.Lock()
        logger.info("partitioned_vector_store_init", dim=dim)

    def get_partition(self, tenant_id: str) -> LocalVectorStore:
        """Get or create a tenant-specific partition."""
        with self._lock:
            if tenant_id not in self._partitions:
                self._partitions[tenant_id] = LocalVectorStore(self._dim)
                logger.info("partition_created", tenant_id=tenant_id)
            return self._partitions[tenant_id]

    @property
    def global_wisdom(self) -> LocalVectorStore:
        """The shared global Wisdom Nugget index."""
        return self._global_wisdom

    def add_to_partition(self, tenant_id: str, docs: List[VectorDocument]) -> int:
        """Add documents to a tenant-specific partition."""
        store = self.get_partition(tenant_id)
        return store.add_documents(docs)

    def add_to_global(self, docs: List[VectorDocument]) -> int:
        """Add documents to the global Wisdom index."""
        return self._global_wisdom.add_documents(docs)

    def search_partition(self, tenant_id: str, query: str, top_k: int = 10) -> List[SearchResult]:
        """Search within a specific tenant's partition."""
        store = self.get_partition(tenant_id)
        return store.search(query, top_k)

    def search_global(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """Search the global Wisdom index."""
        return self._global_wisdom.search(query, top_k)

    def search_all(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """Search across ALL partitions and global. Merges by score."""
        all_results: List[SearchResult] = []
        all_results.extend(self._global_wisdom.search(query, top_k))
        with self._lock:
            partition_ids = list(self._partitions.keys())
        for tid in partition_ids:
            results = self.search_partition(tid, query, top_k)
            all_results.extend(results)
        all_results.sort(key=lambda r: r.score, reverse=True)
        return all_results[:top_k]

    def remove_partition(self, tenant_id: str) -> bool:
        """Remove an entire tenant partition."""
        with self._lock:
            if tenant_id in self._partitions:
                self._partitions[tenant_id].clear()
                del self._partitions[tenant_id]
                logger.info("partition_removed", tenant_id=tenant_id)
                return True
            return False

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            partition_stats = {}
            total_docs = 0
            for tid, store in self._partitions.items():
                s = store.stats()
                partition_stats[tid] = s
                total_docs += s["documentCount"]
            global_stats = self._global_wisdom.stats()
            total_docs += global_stats["documentCount"]
        return {
            "totalDocuments": total_docs,
            "partitionCount": len(partition_stats),
            "globalWisdom": global_stats,
            "partitions": partition_stats,
            "dimension": self._dim,
        }

    def clear_all(self) -> int:
        """Clear all partitions and global index."""
        count = 0
        with self._lock:
            for store in self._partitions.values():
                count += store.count
                store.clear()
            self._partitions.clear()
        count += self._global_wisdom.count
        self._global_wisdom.clear()
        return count


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_store: Optional[LocalVectorStore] = None
_store_lock = threading.Lock()


def get_local_vector_store(dim: int = 256) -> LocalVectorStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = LocalVectorStore(dim)
        return _store


_partitioned_store: Optional[PartitionedVectorStore] = None
_partitioned_lock = threading.Lock()


def get_partitioned_vector_store(dim: int = 256) -> PartitionedVectorStore:
    """Get or create the partitioned (multi-tenant) vector store."""
    global _partitioned_store
    with _partitioned_lock:
        if _partitioned_store is None:
            _partitioned_store = PartitionedVectorStore(dim)
        return _partitioned_store
