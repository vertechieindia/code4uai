"""Consensus Engine — Worker-Critic-Judge architecture.

The ``ReviewOrchestrator`` coordinates the quality pipeline:

  1. **Static Guardrails** — deterministic hard stops (secrets, eval).
     If triggered, the plan is rejected immediately.
  2. **Critic Agent** — heuristic + AST review producing a score (1-10)
     and a list of violations.
  3. **Consensus Decision** — if ``score >= threshold`` (default 7),
     the plan is approved.  If not, the orchestrator can request a
     Worker retry with the Critic's feedback.

The Judge (a higher-reasoning model) is invoked only when Worker and
Critic disagree on borderline cases.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import structlog

from code4u.agents.review.critic import CriticAgent, CriticReview, Violation
from code4u.core.guardrails import StaticGuardrail, GuardrailViolation, GuardrailResult

logger = structlog.get_logger("consensus")


class Verdict(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    RETRY = "retry"
    GUARDRAIL_BLOCK = "guardrail_block"


@dataclass
class ReviewRound:
    """Record of a single review iteration."""
    round_number: int
    critic_review: Optional[CriticReview] = None
    guardrail_result: Optional[GuardrailResult] = None
    verdict: Verdict = Verdict.REJECTED
    feedback: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "round": self.round_number,
            "verdict": self.verdict.value,
            "feedback": self.feedback,
            "criticScore": self.critic_review.score if self.critic_review else None,
            "criticPassed": self.critic_review.passed if self.critic_review else None,
            "guardrailPassed": self.guardrail_result.passed if self.guardrail_result else None,
            "violations": (
                [v.to_dict() for v in self.critic_review.violations]
                if self.critic_review else []
            ),
        }


@dataclass
class ConsensusResult:
    """Final outcome of the full review pipeline."""
    verdict: Verdict
    rounds: List[ReviewRound] = field(default_factory=list)
    final_score: int = 0
    total_violations: int = 0
    guardrail_violations: int = 0
    duration_ms: float = 0.0

    @property
    def approved(self) -> bool:
        return self.verdict == Verdict.APPROVED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "approved": self.approved,
            "finalScore": self.final_score,
            "totalViolations": self.total_violations,
            "guardrailViolations": self.guardrail_violations,
            "durationMs": round(self.duration_ms, 1),
            "rounds": [r.to_dict() for r in self.rounds],
        }


class ReviewOrchestrator:
    """Coordinates the Worker → Guardrail → Critic → Judge pipeline.

    Usage::

        orchestrator = ReviewOrchestrator()
        result = orchestrator.review(proposed_plan.operations)
        if not result.approved:
            # reject or retry
            ...

    With retry loop::

        result = orchestrator.review_with_retry(
            operations=plan.operations,
            retry_fn=lambda feedback: worker.regenerate(feedback),
            max_retries=2,
        )
    """

    def __init__(
        self,
        threshold: int = 7,
        strict_guardrails: bool = True,
    ) -> None:
        self._threshold = threshold
        self._critic = CriticAgent(threshold=threshold)
        self._guardrail = StaticGuardrail(strict=strict_guardrails)

    def review(self, operations: list) -> ConsensusResult:
        """Run the full review pipeline on a set of operations.

        Steps:
          1. Static guardrails (hard stops).
          2. Critic review (scoring + violations).
          3. Consensus verdict.
        """
        t0 = time.monotonic()
        round_rec = ReviewRound(round_number=1)

        # Phase 1: Static guardrails
        try:
            gr_result = self._guardrail.scan_plan(operations)
            round_rec.guardrail_result = gr_result
        except GuardrailViolation as exc:
            round_rec.guardrail_result = GuardrailResult(
                passed=False,
                violations=[exc.to_dict()],
            )
            round_rec.verdict = Verdict.GUARDRAIL_BLOCK
            round_rec.feedback = str(exc)

            return ConsensusResult(
                verdict=Verdict.GUARDRAIL_BLOCK,
                rounds=[round_rec],
                guardrail_violations=1,
                duration_ms=(time.monotonic() - t0) * 1000,
            )

        if not gr_result.passed:
            round_rec.verdict = Verdict.GUARDRAIL_BLOCK
            round_rec.feedback = "; ".join(
                v.get("message", "") for v in gr_result.violations
            )
            return ConsensusResult(
                verdict=Verdict.GUARDRAIL_BLOCK,
                rounds=[round_rec],
                guardrail_violations=len(gr_result.violations),
                duration_ms=(time.monotonic() - t0) * 1000,
            )

        # Phase 2: Critic review
        critic_review = self._critic.review_plan(operations)
        round_rec.critic_review = critic_review

        # Phase 3: Verdict
        if critic_review.passed:
            round_rec.verdict = Verdict.APPROVED
            round_rec.feedback = critic_review.summary
        else:
            round_rec.verdict = Verdict.REJECTED
            round_rec.feedback = self._build_retry_feedback(critic_review)

        result = ConsensusResult(
            verdict=round_rec.verdict,
            rounds=[round_rec],
            final_score=critic_review.score,
            total_violations=len(critic_review.violations),
            duration_ms=(time.monotonic() - t0) * 1000,
        )

        logger.info(
            "consensus_reached",
            verdict=result.verdict.value,
            score=result.final_score,
            violations=result.total_violations,
        )

        return result

    def review_with_retry(
        self,
        operations: list,
        retry_fn: Optional[Callable[[str], list]] = None,
        max_retries: int = 2,
    ) -> ConsensusResult:
        """Review with automatic retry loop.

        If the Critic rejects the plan and ``retry_fn`` is provided,
        the orchestrator passes the Critic's feedback to the Worker
        for a second (or third) attempt.

        Args:
            operations: Initial operations to review.
            retry_fn: Callable that takes feedback string and returns
                      new operations list. If None, no retries.
            max_retries: Maximum retry attempts.

        Returns:
            ``ConsensusResult`` with all rounds recorded.
        """
        t0 = time.monotonic()
        all_rounds: List[ReviewRound] = []
        current_ops = operations

        for attempt in range(1, max_retries + 2):  # +1 for initial, +1 for max
            round_rec = ReviewRound(round_number=attempt)

            # Guardrails
            try:
                gr_result = self._guardrail.scan_plan(current_ops)
                round_rec.guardrail_result = gr_result
            except GuardrailViolation as exc:
                round_rec.guardrail_result = GuardrailResult(
                    passed=False, violations=[exc.to_dict()],
                )
                round_rec.verdict = Verdict.GUARDRAIL_BLOCK
                round_rec.feedback = str(exc)
                all_rounds.append(round_rec)
                return ConsensusResult(
                    verdict=Verdict.GUARDRAIL_BLOCK,
                    rounds=all_rounds,
                    guardrail_violations=1,
                    duration_ms=(time.monotonic() - t0) * 1000,
                )

            if not gr_result.passed:
                round_rec.verdict = Verdict.GUARDRAIL_BLOCK
                all_rounds.append(round_rec)
                return ConsensusResult(
                    verdict=Verdict.GUARDRAIL_BLOCK,
                    rounds=all_rounds,
                    guardrail_violations=len(gr_result.violations),
                    duration_ms=(time.monotonic() - t0) * 1000,
                )

            # Critic
            critic_review = self._critic.review_plan(current_ops)
            round_rec.critic_review = critic_review

            if critic_review.passed:
                round_rec.verdict = Verdict.APPROVED
                round_rec.feedback = critic_review.summary
                all_rounds.append(round_rec)

                return ConsensusResult(
                    verdict=Verdict.APPROVED,
                    rounds=all_rounds,
                    final_score=critic_review.score,
                    total_violations=len(critic_review.violations),
                    duration_ms=(time.monotonic() - t0) * 1000,
                )

            # Rejected — can we retry?
            feedback = self._build_retry_feedback(critic_review)
            round_rec.verdict = Verdict.RETRY if (retry_fn and attempt <= max_retries) else Verdict.REJECTED
            round_rec.feedback = feedback
            all_rounds.append(round_rec)

            if not retry_fn or attempt > max_retries:
                break

            # Retry with Worker feedback
            logger.info(
                "consensus_retry",
                attempt=attempt,
                score=critic_review.score,
                feedback_len=len(feedback),
            )
            current_ops = retry_fn(feedback)

        final_score = all_rounds[-1].critic_review.score if all_rounds[-1].critic_review else 0
        total_v = len(all_rounds[-1].critic_review.violations) if all_rounds[-1].critic_review else 0

        return ConsensusResult(
            verdict=Verdict.REJECTED,
            rounds=all_rounds,
            final_score=final_score,
            total_violations=total_v,
            duration_ms=(time.monotonic() - t0) * 1000,
        )

    def _build_retry_feedback(self, review: CriticReview) -> str:
        """Build actionable feedback for the Worker's retry."""
        parts = [
            f"Quality score: {review.score}/10 (minimum {self._threshold} required).",
            "Issues to fix:",
        ]
        for v in review.violations:
            parts.append(
                f"  [{v.severity.value.upper()}] {v.rule_id}: "
                f"{v.message} (line {v.line_number})"
            )
        return "\n".join(parts)
