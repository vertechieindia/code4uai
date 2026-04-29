"""Model Distillation — collect successful refactors for fine-tuning.

Captures every successful swarm execution as a training example:
  - Input: the natural language goal + workspace context
  - Output: the generated plan + applied code changes

These examples are stored in JSONL format suitable for fine-tuning
smaller models (Llama-3-8B, Qwen-2.5-Coder, etc.) so the local
"Heal" agent can eventually match or exceed cloud model quality.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger("distillation")

_EXPORT_DIR = os.getenv("DISTILL_EXPORT_DIR", "/tmp/code4u-distillation")


# ---------------------------------------------------------------------------
# Training example schema
# ---------------------------------------------------------------------------

@dataclass
class TrainingExample:
    """One input/output pair for fine-tuning."""
    id: str = ""
    timestamp: float = field(default_factory=time.time)
    agent_type: str = ""
    model_used: str = ""
    complexity: str = "low"

    system_prompt: str = ""
    user_input: str = ""
    assistant_output: str = ""

    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: float = 0.0
    success: bool = True

    goal: str = ""
    workspace_path: str = ""
    files_changed: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Distillation store
# ---------------------------------------------------------------------------

class DistillationStore:
    """Collects training examples from successful executions.

    Examples are kept in memory and can be exported to JSONL for
    model fine-tuning via the API.
    """

    def __init__(self) -> None:
        self._examples: List[TrainingExample] = []
        self._lock = threading.Lock()

    @property
    def count(self) -> int:
        return len(self._examples)

    def add(self, example: TrainingExample) -> None:
        with self._lock:
            if not example.id:
                raw = f"{example.timestamp}-{example.goal[:50]}-{example.agent_type}"
                example.id = hashlib.sha256(raw.encode()).hexdigest()[:16]
            self._examples.append(example)
            logger.info(
                "distillation_example_added",
                id=example.id,
                agent=example.agent_type,
                model=example.model_used,
            )

    def collect_from_telemetry(self) -> int:
        """Pull successful executions from TelemetryStore as training examples."""
        from code4u.platform_core.telemetry import get_telemetry_store

        store = get_telemetry_store()
        records = store.get_recent(limit=100)
        existing_ids = {e.id for e in self._examples}
        added = 0

        for rec in records:
            if not rec.get("success", False):
                continue
            eid = f"tel-{rec.get('id', '')}"
            if eid in existing_ids:
                continue

            self.add(TrainingExample(
                id=eid,
                agent_type=rec.get("agent", ""),
                model_used=rec.get("model", ""),
                user_input=rec.get("description", ""),
                assistant_output="[telemetry record — see execution logs]",
                input_tokens=rec.get("tokens", 0) // 2,
                output_tokens=rec.get("tokens", 0) // 2,
                duration_ms=rec.get("durationMs", 0),
                goal=rec.get("description", ""),
                success=True,
            ))
            added += 1

        return added

    def get_examples(
        self,
        limit: int = 100,
        agent_type: str = "",
        success_only: bool = True,
    ) -> List[TrainingExample]:
        with self._lock:
            filtered = self._examples
            if success_only:
                filtered = [e for e in filtered if e.success]
            if agent_type:
                filtered = [e for e in filtered if e.agent_type == agent_type]
            return sorted(filtered, key=lambda e: e.timestamp, reverse=True)[:limit]

    def export_jsonl(self, path: str = "") -> str:
        """Export all examples to JSONL (OpenAI fine-tuning format)."""
        if not path:
            os.makedirs(_EXPORT_DIR, exist_ok=True)
            path = os.path.join(_EXPORT_DIR, f"distill-{int(time.time())}.jsonl")

        examples = self.get_examples(limit=10000)
        with open(path, "w") as f:
            for ex in examples:
                entry = {
                    "messages": [
                        {"role": "system", "content": ex.system_prompt or f"You are a {ex.agent_type} agent for code4u.ai."},
                        {"role": "user", "content": ex.user_input or ex.goal},
                        {"role": "assistant", "content": ex.assistant_output},
                    ],
                    "metadata": {
                        "id": ex.id,
                        "agent_type": ex.agent_type,
                        "model_used": ex.model_used,
                        "complexity": ex.complexity,
                        "duration_ms": ex.duration_ms,
                    },
                }
                f.write(json.dumps(entry) + "\n")

        logger.info("distillation_exported", path=path, count=len(examples))
        return path

    def export_chat_format(self) -> List[Dict[str, Any]]:
        """Export as chat-format dicts for API consumption."""
        return [
            {
                "id": ex.id,
                "messages": [
                    {"role": "system", "content": ex.system_prompt or f"You are a {ex.agent_type} agent."},
                    {"role": "user", "content": ex.user_input or ex.goal},
                    {"role": "assistant", "content": ex.assistant_output},
                ],
                "agent_type": ex.agent_type,
                "model_used": ex.model_used,
                "complexity": ex.complexity,
                "timestamp": ex.timestamp,
            }
            for ex in self.get_examples(limit=500)
        ]

    def stats(self) -> Dict[str, Any]:
        by_agent: Dict[str, int] = {}
        by_model: Dict[str, int] = {}
        by_complexity: Dict[str, int] = {}
        for ex in self._examples:
            by_agent[ex.agent_type] = by_agent.get(ex.agent_type, 0) + 1
            by_model[ex.model_used] = by_model.get(ex.model_used, 0) + 1
            by_complexity[ex.complexity] = by_complexity.get(ex.complexity, 0) + 1

        return {
            "totalExamples": self.count,
            "successOnly": sum(1 for e in self._examples if e.success),
            "byAgent": by_agent,
            "byModel": by_model,
            "byComplexity": by_complexity,
        }

    def clear(self) -> None:
        with self._lock:
            self._examples.clear()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_store: Optional[DistillationStore] = None
_store_lock = threading.Lock()


def get_distillation_store() -> DistillationStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = DistillationStore()
        return _store
