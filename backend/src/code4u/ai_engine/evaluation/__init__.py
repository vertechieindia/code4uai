from __future__ import annotations
"""Evaluation & Benchmark Harness for code4u.ai.

This is how you prove you're better than Cursor.

Evaluation Categories:
- Correctness: Diff applies cleanly, tests pass, types validate
- Scope Discipline: No extra files, no API invention
- Determinism: Same input → same diff
- Cost: Tokens per task, GPU seconds
"""
from code4u.ai_engine.evaluation.runner import EvaluationRunner, EvaluationResult
from code4u.ai_engine.evaluation.scorer import Scorer, EvaluationScore
from code4u.ai_engine.evaluation.golden_dataset import GoldenDataset, EvaluationCase

__all__ = [
    "EvaluationRunner",
    "EvaluationResult",
    "Scorer",
    "EvaluationScore",
    "GoldenDataset",
    "EvaluationCase",
]

