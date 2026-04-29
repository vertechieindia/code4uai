from __future__ import annotations
"""Evaluation runner for code4u.ai benchmarks."""
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
import json
import structlog

from code4u.ai_engine.evaluation.golden_dataset import (
    GoldenDataset,
    EvaluationCase,
    EvaluationCategory,
)
from code4u.ai_engine.evaluation.scorer import Scorer, EvaluationScore, BenchmarkResult

logger = structlog.get_logger("evaluation.runner")


@dataclass
class EvaluationResult:
    """Result of a single evaluation run."""
    case_id: str
    success: bool
    score: EvaluationScore | None = None
    error: Optional[str] = None
    
    # Raw data
    input_prompt: str = ""
    actual_output: Dict[str, Any] = field(default_factory=dict)
    expected_diff: str = ""
    
    # Execution info
    execution_time_ms: float = 0
    tokens_used: int = 0
    model_used: str = ""


@dataclass
class EvaluationRun:
    """Complete evaluation run."""
    run_id: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    results: list[EvaluationResult] = field(default_factory=list)
    benchmark: BenchmarkResult | None = None
    
    # Version info
    model_version: str = ""
    lora_version: str = ""
    prompt_version: str = ""
    
    def save(self, output_dir: str = "./eval_results"):
        """Save evaluation run to disk."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        run_file = output_path / f"run_{self.run_id}.json"
        run_file.write_text(json.dumps({
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "model_version": self.model_version,
            "lora_version": self.lora_version,
            "prompt_version": self.prompt_version,
            "results": [
                {
                    "case_id": r.case_id,
                    "success": r.success,
                    "score": r.score.to_dict() if r.score else None,
                    "error": r.error,
                    "execution_time_ms": r.execution_time_ms,
                    "tokens_used": r.tokens_used,
                }
                for r in self.results
            ],
            "benchmark": {
                "pass_rate": self.benchmark.pass_rate if self.benchmark else 0,
                "avg_correctness": self.benchmark.avg_correctness if self.benchmark else 0,
                "avg_scope_discipline": self.benchmark.avg_scope_discipline if self.benchmark else 0,
            } if self.benchmark else None
        }, indent=2))
        
        logger.info("run_saved", path=str(run_file))


class EvaluationRunner:
    """
    Run evaluations against golden dataset.
    
    Metrics are stored per:
    - Model version
    - LoRA version
    - Prompt version
    
    This enables regression detection.
    """
    
    def __init__(
        self,
        dataset: GoldenDataset | None = None,
        scorer: Scorer | None = None
    ):
        self.dataset = dataset or GoldenDataset()
        self.scorer = scorer or Scorer()
    
    async def run(
        self,
        categories: list[EvaluationCategory] | None = None,
        case_ids: List[str] | None = None,
        model_version: str = "",
        lora_version: str = "",
        prompt_version: str = ""
    ) -> EvaluationRun:
        """
        Run evaluation on specified cases.
        
        Args:
            categories: Categories to evaluate (all if None)
            case_ids: Specific cases to run (all if None)
            model_version: Version of base model
            lora_version: Version of LoRA adapter
            prompt_version: Version of prompt compiler
        """
        import uuid
        import time
        
        run_id = str(uuid.uuid4())[:8]
        run = EvaluationRun(
            run_id=run_id,
            model_version=model_version,
            lora_version=lora_version,
            prompt_version=prompt_version
        )
        
        # Get cases to run
        cases = self._get_cases(categories, case_ids)
        
        logger.info(
            "evaluation_started",
            run_id=run_id,
            case_count=len(cases)
        )
        
        scores: list[EvaluationScore] = []
        
        for case in cases:
            start = time.perf_counter()
            
            try:
                # Execute case
                result = await self._execute_case(case, model_version)
                
                # Score result
                if result.actual_output:
                    score = self.scorer.score(
                        case=case,
                        actual_output=result.actual_output,
                        metadata={
                            "model_version": model_version,
                            "lora_version": lora_version,
                            "prompt_version": prompt_version,
                            "tokens_used": result.tokens_used,
                            "latency_ms": result.execution_time_ms,
                        }
                    )
                    result.score = score
                    scores.append(score)
                
                result.execution_time_ms = (time.perf_counter() - start) * 1000
                run.results.append(result)
                
            except Exception as e:
                logger.error(
                    "case_failed",
                    case_id=case.case_id,
                    error=str(e)
                )
                run.results.append(EvaluationResult(
                    case_id=case.case_id,
                    success=False,
                    error=str(e),
                    execution_time_ms=(time.perf_counter() - start) * 1000
                ))
        
        # Aggregate results
        run.benchmark = self.scorer.aggregate(scores)
        
        logger.info(
            "evaluation_complete",
            run_id=run_id,
            pass_rate=run.benchmark.pass_rate if run.benchmark else 0
        )
        
        return run
    
    def _get_cases(
        self,
        categories: list[EvaluationCategory] | None,
        case_ids: List[str] | None
    ) -> list[EvaluationCase]:
        """Get cases to evaluate."""
        if case_ids:
            return [
                self.dataset.get_case(cid)
                for cid in case_ids
                if self.dataset.get_case(cid)
            ]
        
        if categories:
            cases = []
            for cat in categories:
                cases.extend(self.dataset.get_cases_by_category(cat))
            return cases
        
        return self.dataset.get_all_cases()
    
    async def _execute_case(
        self,
        case: EvaluationCase,
        model_version: str
    ) -> EvaluationResult:
        """Execute a single evaluation case."""
        from code4u.ai_engine.compiler.prompt_compiler import PromptCompiler
        from code4u.ai_engine.compiler.types import (
            CompilerInput, IntentType, LanguageProfile, ChangePlan, GraphNode
        )
        
        # Build compiler input from case
        language = case.context.get("language", "python")
        frameworks = case.context.get("frameworks", [])
        
        # Convert input files to graph nodes
        nodes = [
            GraphNode(
                node_id=f"node-{i}",
                node_type="module",
                name=path.split("/")[-1],
                path=path,
                content=content
            )
            for i, (path, content) in enumerate(case.input_files.items())
        ]
        
        compiler_input = CompilerInput(
            intent=self._map_category_to_intent(case.category),
            target_node_id=nodes[0].node_id if nodes else "",
            change_plan=ChangePlan(
                plan_id="eval",
                steps=[],
                affected_node_ids=[n.node_id for n in nodes]
            ),
            impacted_nodes=nodes,
            constraints=[],
            ownership=[],
            language_profile=LanguageProfile(
                language=language,
                frameworks=frameworks
            ),
            user_instruction=case.instruction
        )
        
        # Compile prompt
        compiler = PromptCompiler()
        bundle = compiler.compile(compiler_input)
        
        # In production, this would call the LLM executor
        # For now, return a mock result
        return EvaluationResult(
            case_id=case.case_id,
            success=True,
            input_prompt=bundle.user_prompt,
            actual_output={"diffs": []},  # Would be LLM output
            expected_diff=case.expected.diff,
            model_used=model_version,
            tokens_used=bundle.scope_summary.get("estimated_tokens", 0),
        )
    
    def _map_category_to_intent(self, category: EvaluationCategory) -> IntentType:
        """Map evaluation category to intent type."""
        from code4u.ai_engine.compiler.types import IntentType
        
        mapping = {
            EvaluationCategory.REFACTOR: IntentType.REFACTOR,
            EvaluationCategory.RENAME: IntentType.RENAME,
            EvaluationCategory.EXTRACT: IntentType.EXTRACT,
            EvaluationCategory.API_EVOLUTION: IntentType.ADD_API,
            EvaluationCategory.SCHEMA_MIGRATION: IntentType.MIGRATE,
        }
        
        return mapping.get(category, IntentType.REFACTOR)
    
    def compare_runs(
        self,
        run_a: EvaluationRun,
        run_b: EvaluationRun
    ) -> Dict[str, Any]:
        """Compare two evaluation runs for regression detection."""
        if not run_a.benchmark or not run_b.benchmark:
            return {"error": "Missing benchmark data"}
        
        a = run_a.benchmark
        b = run_b.benchmark
        
        return {
            "pass_rate_delta": b.pass_rate - a.pass_rate,
            "correctness_delta": b.avg_correctness - a.avg_correctness,
            "scope_delta": b.avg_scope_discipline - a.avg_scope_discipline,
            "tokens_delta": b.avg_tokens - a.avg_tokens,
            "latency_delta": b.avg_latency_ms - a.avg_latency_ms,
            "regression_detected": (
                b.pass_rate < a.pass_rate * 0.95 or
                b.avg_correctness < a.avg_correctness * 0.95
            )
        }

