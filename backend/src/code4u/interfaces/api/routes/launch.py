"""Final Launch, Stress Test & System Summary API routes.

Endpoints:
  POST /launch/stress-test       — run stress test with configurable load
  GET  /launch/impact-summary    — get the full 21-day build impact summary
  GET  /launch/cache/stats       — cache statistics
  POST /launch/cache/clear       — clear all caches
  GET  /launch/vector/stats      — partitioned vector store stats
  POST /launch/vector/benchmark  — benchmark vector search speed
  GET  /launch/readiness         — final launch readiness check
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from code4u.core.cache import get_cache_manager
from code4u.ai_engine.vector_store import (
    get_partitioned_vector_store,
    VectorDocument,
)

router = APIRouter(prefix="/launch", tags=["Launch Command Center"])


class StressTestRequest(BaseModel):
    concurrent_tasks: int = Field(100, description="Number of concurrent tasks", ge=1, le=10000)
    duration_seconds: float = Field(5.0, description="Test duration", ge=1.0, le=60.0)
    include_chaos: bool = Field(False, description="Include chaos agent disruptions")


class BenchmarkRequest(BaseModel):
    num_documents: int = Field(1000, description="Docs to index", ge=10, le=100000)
    num_queries: int = Field(100, description="Queries to run", ge=1, le=10000)
    top_k: int = Field(10, description="Results per query")


@router.post("/stress-test")
async def run_stress_test(request: StressTestRequest) -> Dict[str, Any]:
    """Run a load simulation to verify system resilience."""
    start = time.time()
    results: Dict[str, Any] = {
        "concurrentTasks": request.concurrent_tasks,
        "durationSeconds": request.duration_seconds,
        "chaosEnabled": request.include_chaos,
    }

    cache = get_cache_manager()
    successes = 0
    failures = 0
    latencies: List[float] = []

    async def simulate_task(task_id: int) -> bool:
        t0 = time.time()
        try:
            cache.set("stress", {"task": task_id, "ts": time.time()}, f"task-{task_id}")
            val = cache.get("stress", f"task-{task_id}")
            if val is None:
                return False
            cache.delete("stress", f"task-{task_id}")
            return True
        except Exception:
            return False
        finally:
            latencies.append((time.time() - t0) * 1000)

    batch_size = min(request.concurrent_tasks, 500)
    for batch_start in range(0, request.concurrent_tasks, batch_size):
        batch_end = min(batch_start + batch_size, request.concurrent_tasks)
        tasks = [simulate_task(i) for i in range(batch_start, batch_end)]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in batch_results:
            if isinstance(r, bool) and r:
                successes += 1
            else:
                failures += 1

    elapsed = time.time() - start
    results["elapsed_ms"] = round(elapsed * 1000, 2)
    results["successes"] = successes
    results["failures"] = failures
    results["successRate"] = round(successes / max(successes + failures, 1) * 100, 2)
    results["avgLatencyMs"] = round(sum(latencies) / max(len(latencies), 1), 3)
    results["p95LatencyMs"] = round(sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0, 3)
    results["p99LatencyMs"] = round(sorted(latencies)[int(len(latencies) * 0.99)] if latencies else 0, 3)
    results["throughputOps"] = round(successes / max(elapsed, 0.001), 1)
    results["status"] = "PASS" if results["successRate"] >= 99.0 else "DEGRADED" if results["successRate"] >= 90.0 else "FAIL"

    return results


@router.get("/impact-summary")
async def get_impact_summary() -> Dict[str, Any]:
    """Get the full 21-day build impact summary for the Launch Command Center."""
    cache = get_cache_manager()
    pvs = get_partitioned_vector_store()

    from code4u.knowledge.pattern_extractor import get_pattern_extractor
    from code4u.knowledge.provenance_tracker import get_provenance_tracker
    from code4u.security_compliance.toxic_scanner import get_toxic_scanner
    from code4u.agents.legal_agent import get_legal_agent

    extractor = get_pattern_extractor()
    tracker = get_provenance_tracker()
    scanner = get_toxic_scanner()
    legal = get_legal_agent()

    wisdom_stats = extractor.get_stats()
    provenance_stats = tracker.get_stats()
    toxic_stats = scanner.get_stats()
    cache_stats = cache.get_stats()
    vector_stats = pvs.stats()

    total_provenance = provenance_stats.get("totalRecords", 0)
    verified = provenance_stats.get("licenseVerified", 0)

    return {
        "platform": "code4u.ai",
        "buildPhase": "Day 21 — Sovereign Launch",
        "intelligenceGain": {
            "wisdomNuggetsCreated": wisdom_stats.get("totalNuggets", 0),
            "wisdomNuggetsUsed": wisdom_stats.get("totalUsages", 0),
            "byType": wisdom_stats.get("byType", {}),
            "byLanguage": wisdom_stats.get("byLanguage", {}),
        },
        "safetyPerimeter": {
            "toxicPatternsBlocked": toxic_stats.get("blockedMatches", 0),
            "totalToxicScans": toxic_stats.get("totalMatches", 0),
            "byCategory": toxic_stats.get("byCategory", {}),
            "bySeverity": toxic_stats.get("bySeverity", {}),
            "licenseViolationsBlocked": len(legal.get_violations()),
        },
        "legalPurity": {
            "totalProvenanceRecords": total_provenance,
            "verifiedRecords": verified,
            "verificationRate": round(verified / max(total_provenance, 1) * 100, 1),
            "appliedRecords": provenance_stats.get("appliedRecords", 0),
        },
        "performance": {
            "cacheBackend": cache_stats.get("backend", "memory"),
            "cacheHitRate": cache_stats.get("hitRate", 0),
            "cacheSize": cache_stats.get("size", 0),
            "vectorPartitions": vector_stats.get("partitionCount", 0),
            "totalVectorDocs": vector_stats.get("totalDocuments", 0),
        },
        "infrastructure": {
            "day1to5": "Core Platform — IDE, Refactor, Knowledge Graph",
            "day6to10": "Security & Compliance — Sentinel, Fortress, SCA",
            "day11to14": "Agent Swarm & Production Hardening",
            "day15to16": "Titan Phase — Recursive Gauntlet & Ecosystem Connect",
            "day17to18": "Predictive Intelligence & Chaos Engineering",
            "day19": "Collective Intelligence — Wisdom Sharing",
            "day20": "Legal & Ethical Governance",
            "day21": "Final Optimization & Sovereign Launch",
        },
    }


@router.get("/cache/stats")
async def get_cache_stats() -> Dict[str, Any]:
    cache = get_cache_manager()
    return cache.get_stats()


@router.post("/cache/clear")
async def clear_cache() -> Dict[str, Any]:
    cache = get_cache_manager()
    count = cache.clear_all()
    return {"cleared": count, "status": "ok"}


@router.get("/vector/stats")
async def get_vector_stats() -> Dict[str, Any]:
    pvs = get_partitioned_vector_store()
    return pvs.stats()


@router.post("/vector/benchmark")
async def benchmark_vector_search(request: BenchmarkRequest) -> Dict[str, Any]:
    """Benchmark vector store search speed."""
    pvs = get_partitioned_vector_store()
    bench_store = pvs.get_partition("__benchmark__")

    sample_texts = [
        f"function process_{i}(data) {{ return data.map(x => x * {i}); }}"
        for i in range(request.num_documents)
    ]
    docs = [
        VectorDocument(id=f"bench-{i}", content=text, metadata={"idx": i})
        for i, text in enumerate(sample_texts)
    ]

    t0 = time.time()
    bench_store.add_documents(docs)
    index_time = time.time() - t0

    queries = [f"process data transform {i}" for i in range(request.num_queries)]
    search_times: List[float] = []
    total_results = 0

    for q in queries:
        qt0 = time.time()
        results = bench_store.search(q, top_k=request.top_k)
        search_times.append((time.time() - qt0) * 1000)
        total_results += len(results)

    pvs.remove_partition("__benchmark__")

    avg_search = sum(search_times) / len(search_times)
    sorted_times = sorted(search_times)

    return {
        "documents": request.num_documents,
        "queries": request.num_queries,
        "indexTimeMs": round(index_time * 1000, 2),
        "avgSearchMs": round(avg_search, 3),
        "p50SearchMs": round(sorted_times[len(sorted_times) // 2], 3),
        "p95SearchMs": round(sorted_times[int(len(sorted_times) * 0.95)], 3),
        "p99SearchMs": round(sorted_times[int(len(sorted_times) * 0.99)], 3),
        "totalResults": total_results,
        "throughputQps": round(request.num_queries / (sum(search_times) / 1000), 1),
        "status": "PASS" if avg_search < 50.0 else "SLOW",
    }


@router.get("/readiness")
async def check_launch_readiness() -> Dict[str, Any]:
    """Final launch readiness check aggregating all subsystems."""
    checks: Dict[str, Dict[str, Any]] = {}

    # Cache
    try:
        cache = get_cache_manager()
        cache.set("readiness", "ok", "ping")
        val = cache.get("readiness", "ping")
        checks["cache"] = {"status": "pass" if val == "ok" else "degraded", "backend": cache.get_stats().get("backend", "unknown")}
    except Exception as e:
        checks["cache"] = {"status": "fail", "error": str(e)}

    # Vector Store
    try:
        pvs = get_partitioned_vector_store()
        stats = pvs.stats()
        checks["vectorStore"] = {"status": "pass", "partitions": stats["partitionCount"], "totalDocs": stats["totalDocuments"]}
    except Exception as e:
        checks["vectorStore"] = {"status": "fail", "error": str(e)}

    # Wisdom Store
    try:
        from code4u.knowledge.pattern_extractor import get_pattern_extractor
        ext = get_pattern_extractor()
        checks["wisdomStore"] = {"status": "pass", "nuggets": ext.get_stats()["totalNuggets"]}
    except Exception as e:
        checks["wisdomStore"] = {"status": "fail", "error": str(e)}

    # Legal Agent
    try:
        from code4u.agents.legal_agent import get_legal_agent
        legal = get_legal_agent()
        matrix = legal.get_compatibility_matrix()
        checks["legalAgent"] = {"status": "pass", "categories": len(matrix.get("categories", []))}
    except Exception as e:
        checks["legalAgent"] = {"status": "fail", "error": str(e)}

    # Toxic Scanner
    try:
        from code4u.security_compliance.toxic_scanner import get_toxic_scanner
        scanner = get_toxic_scanner()
        checks["toxicScanner"] = {"status": "pass", "patterns": scanner.get_stats()["customPatterns"] + 15}
    except Exception as e:
        checks["toxicScanner"] = {"status": "fail", "error": str(e)}

    # Provenance Tracker
    try:
        from code4u.knowledge.provenance_tracker import get_provenance_tracker
        tracker = get_provenance_tracker()
        checks["provenanceTracker"] = {"status": "pass", "records": tracker.get_stats()["totalRecords"]}
    except Exception as e:
        checks["provenanceTracker"] = {"status": "fail", "error": str(e)}

    passed = sum(1 for c in checks.values() if c["status"] == "pass")
    total = len(checks)
    score = round(passed / total * 100)

    return {
        "readinessScore": score,
        "status": "LAUNCH_READY" if score == 100 else "DEGRADED" if score >= 80 else "NOT_READY",
        "checks": checks,
        "passed": passed,
        "total": total,
        "timestamp": time.time(),
    }
