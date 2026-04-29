"""Day 22 — Multi-Agent Quality Jury test suite.

Tests:
  - CriticAgent: security patterns, complexity, best-practices, scoring.
  - StaticGuardrail: forbidden patterns, strict/lenient modes.
  - ReviewOrchestrator: consensus pipeline, retry loop.
  - End-to-end: secret catch, critic veto, retry improvement.
  - API endpoints: review, guardrails, consensus.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from typing import List

import pytest

from code4u.agents.review.critic import (
    CriticAgent,
    CriticReview,
    Violation,
    Severity,
    Category,
)
from code4u.core.guardrails import (
    StaticGuardrail,
    GuardrailViolation,
    GuardrailResult,
)
from code4u.core.consensus import (
    ReviewOrchestrator,
    ConsensusResult,
    Verdict,
    ReviewRound,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class MockOp:
    file_path: str = "test.py"
    content: str = ""
    action: str = "edit"
    original_content: str = ""


CLEAN_CODE = textwrap.dedent("""\
    def calculate_total(items):
        return sum(item.price for item in items)

    def get_user(uid):
        return db.query(User).filter(User.id == uid).first()
""")

EVAL_CODE = textwrap.dedent("""\
    def run_command(cmd):
        return eval(cmd)
""")

EXEC_CODE = textwrap.dedent("""\
    def apply_patch(code):
        exec(code)
""")

SHELL_CODE = textwrap.dedent("""\
    import subprocess
    subprocess.run(f"rm -rf {path}", shell=True)
""")

SECRET_CODE = textwrap.dedent("""\
    AWS_SECRET_ACCESS_KEY = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'
    api_key = 'sk-1234567890abcdefghij'
""")

PASSWORD_CODE = textwrap.dedent("""\
    Password = 'SuperSecret123!'
    db_url = "postgres://admin:mypassword@localhost/db"
""")

SQL_INJECTION_CODE = textwrap.dedent("""\
    def get_user(name):
        query = f"SELECT * FROM users WHERE name = '{name}'"
        return db.execute(query)
""")

NESTED_LOOP_CODE = textwrap.dedent("""\
    def find_duplicates(items):
        dupes = []
        for i in items:
            for j in items:
                if i == j:
                    dupes.append(i)
        return dupes
""")

BARE_EXCEPT_CODE = textwrap.dedent("""\
    def risky():
        try:
            do_something()
        except:
            pass
""")

MUTABLE_DEFAULT_CODE = textwrap.dedent("""\
    def add_item(item, items=[]):
        items.append(item)
        return items
""")

PICKLE_CODE = textwrap.dedent("""\
    import pickle
    data = pickle.loads(raw_bytes)
""")

XSS_CODE = textwrap.dedent("""\
    element.innerHTML = userInput;
""")


# ═══════════════════════════════════════════════════════════════════════════
# CriticAgent tests
# ═══════════════════════════════════════════════════════════════════════════

class TestCriticAgent:
    @pytest.fixture
    def critic(self):
        return CriticAgent(threshold=7)

    # -- Security --

    def test_clean_code_passes(self, critic):
        review = critic.review_content(CLEAN_CODE, "utils.py")
        assert review.score >= 7
        assert review.passed

    def test_detects_eval(self, critic):
        review = critic.review_content(EVAL_CODE, "test.py")
        assert not review.passed
        assert any(v.rule_id == "SEC-001" for v in review.violations)

    def test_detects_exec(self, critic):
        review = critic.review_content(EXEC_CODE, "test.py")
        assert any(v.rule_id == "SEC-002" for v in review.violations)

    def test_detects_shell_true(self, critic):
        review = critic.review_content(SHELL_CODE, "test.py")
        assert any(v.rule_id == "SEC-003" for v in review.violations)

    def test_detects_hardcoded_secret(self, critic):
        review = critic.review_content(SECRET_CODE, "config.py")
        sec_violations = review.security_violations
        assert len(sec_violations) >= 1

    def test_detects_password(self, critic):
        review = critic.review_content(PASSWORD_CODE, "config.py")
        assert any("password" in v.message.lower() for v in review.violations)

    def test_detects_sql_injection(self, critic):
        review = critic.review_content(SQL_INJECTION_CODE, "db.py")
        assert any("SQL" in v.message for v in review.violations)

    def test_detects_pickle(self, critic):
        review = critic.review_content(PICKLE_CODE, "loader.py")
        assert any(v.rule_id == "SEC-006" for v in review.violations)

    def test_detects_xss(self, critic):
        review = critic.review_content(XSS_CODE, "component.js")
        assert any("innerHTML" in v.message or "XSS" in v.message for v in review.violations)

    # -- Complexity --

    def test_detects_nested_loops(self, critic):
        review = critic.review_content(NESTED_LOOP_CODE, "utils.py")
        assert any(v.rule_id == "PERF-001" for v in review.violations)

    # -- Best practices --

    def test_detects_bare_except(self, critic):
        review = critic.review_content(BARE_EXCEPT_CODE, "handler.py")
        assert any(v.rule_id == "BP-001" for v in review.violations)

    def test_detects_mutable_default(self, critic):
        review = critic.review_content(MUTABLE_DEFAULT_CODE, "utils.py")
        assert any(v.rule_id == "BP-002" for v in review.violations)

    # -- Scoring --

    def test_critical_lowers_score_heavily(self, critic):
        review = critic.review_content(EVAL_CODE, "test.py")
        assert review.score <= 6  # -4 for critical

    def test_medium_lowers_moderately(self, critic):
        review = critic.review_content(BARE_EXCEPT_CODE, "test.py")
        assert review.score >= 7  # only -1 for medium

    def test_multiple_violations_stack(self, critic):
        code = EVAL_CODE + EXEC_CODE + SHELL_CODE
        review = critic.review_content(code, "test.py")
        assert review.score <= 3

    # -- Plan review --

    def test_review_plan_clean(self, critic):
        ops = [MockOp(content=CLEAN_CODE)]
        review = critic.review_plan(ops)
        assert review.passed

    def test_review_plan_with_issues(self, critic):
        ops = [
            MockOp(content=CLEAN_CODE, file_path="good.py"),
            MockOp(content=EVAL_CODE, file_path="bad.py"),
        ]
        review = critic.review_plan(ops)
        assert not review.passed

    def test_review_plan_skips_deletes(self, critic):
        ops = [MockOp(content=EVAL_CODE, action="delete")]
        review = critic.review_plan(ops)
        assert review.passed

    # -- Diff review --

    def test_review_diff_only_new_code(self, critic):
        old = "x = 1\n"
        new = "x = 1\nresult = eval('2+2')\n"
        review = critic.review_diff(old, new, "test.py")
        assert any(v.rule_id == "SEC-001" for v in review.violations)

    # -- Serialization --

    def test_review_to_dict(self, critic):
        review = critic.review_content(EVAL_CODE, "test.py")
        d = review.to_dict()
        assert "score" in d
        assert "violations" in d
        assert "passed" in d
        assert "criticalCount" in d

    def test_violation_to_dict(self):
        v = Violation(
            rule_id="SEC-001", message="eval", severity=Severity.CRITICAL,
            category=Category.SECURITY, file_path="t.py", line_number=1,
        )
        d = v.to_dict()
        assert d["ruleId"] == "SEC-001"
        assert d["severity"] == "critical"

    def test_summary_text(self, critic):
        review = critic.review_content(EVAL_CODE, "test.py")
        assert "security" in review.summary.lower()


# ═══════════════════════════════════════════════════════════════════════════
# StaticGuardrail tests
# ═══════════════════════════════════════════════════════════════════════════

class TestStaticGuardrail:
    def test_clean_code_passes(self):
        g = StaticGuardrail(strict=False)
        result = g.scan_content(CLEAN_CODE, "utils.py")
        assert result.passed
        assert len(result.violations) == 0

    def test_strict_raises_on_eval(self):
        g = StaticGuardrail(strict=True)
        with pytest.raises(GuardrailViolation) as exc_info:
            g.scan_content(EVAL_CODE, "test.py")
        assert exc_info.value.rule_id == "GR-001"

    def test_strict_raises_on_exec(self):
        g = StaticGuardrail(strict=True)
        with pytest.raises(GuardrailViolation) as exc_info:
            g.scan_content(EXEC_CODE, "test.py")
        assert exc_info.value.rule_id == "GR-002"

    def test_strict_raises_on_shell(self):
        g = StaticGuardrail(strict=True)
        with pytest.raises(GuardrailViolation):
            g.scan_content(SHELL_CODE, "test.py")

    def test_strict_raises_on_secret(self):
        g = StaticGuardrail(strict=True)
        with pytest.raises(GuardrailViolation) as exc_info:
            g.scan_content(SECRET_CODE, "config.py")
        assert "GR-00" in exc_info.value.rule_id

    def test_strict_raises_on_password(self):
        g = StaticGuardrail(strict=True)
        with pytest.raises(GuardrailViolation):
            g.scan_content(PASSWORD_CODE, "config.py")

    def test_lenient_collects_all(self):
        g = StaticGuardrail(strict=False)
        code = EVAL_CODE + EXEC_CODE + SHELL_CODE
        result = g.scan_content(code, "test.py")
        assert not result.passed
        assert len(result.violations) >= 3

    def test_scan_plan(self):
        g = StaticGuardrail(strict=False)
        ops = [MockOp(content=CLEAN_CODE), MockOp(content=EVAL_CODE)]
        result = g.scan_plan(ops)
        assert not result.passed

    def test_scan_plan_strict_raises(self):
        g = StaticGuardrail(strict=True)
        ops = [MockOp(content=CLEAN_CODE), MockOp(content=EVAL_CODE)]
        with pytest.raises(GuardrailViolation):
            g.scan_plan(ops)

    def test_scan_diff_only_new(self):
        g = StaticGuardrail(strict=False)
        old = "x = 1\n"
        new = "x = 1\neval('hello')\n"
        result = g.scan_diff(old, new, "test.py")
        assert not result.passed

    def test_violation_to_dict(self):
        try:
            g = StaticGuardrail(strict=True)
            g.scan_content(EVAL_CODE)
        except GuardrailViolation as exc:
            d = exc.to_dict()
            assert "ruleId" in d
            assert "message" in d

    def test_guardrail_result_to_dict(self):
        g = StaticGuardrail(strict=False)
        result = g.scan_content(EVAL_CODE)
        d = result.to_dict()
        assert "passed" in d
        assert "violations" in d

    def test_detects_pickle(self):
        g = StaticGuardrail(strict=True)
        with pytest.raises(GuardrailViolation):
            g.scan_content(PICKLE_CODE)

    def test_detects_os_system(self):
        g = StaticGuardrail(strict=True)
        with pytest.raises(GuardrailViolation):
            g.scan_content("os.system('rm -rf /')")

    def test_detects_github_token(self):
        g = StaticGuardrail(strict=True)
        code = "token = 'ghp_ABCDEFghijklmnopqrstuvwxyz1234567890ab'"
        with pytest.raises(GuardrailViolation):
            g.scan_content(code)


# ═══════════════════════════════════════════════════════════════════════════
# ReviewOrchestrator tests
# ═══════════════════════════════════════════════════════════════════════════

class TestReviewOrchestrator:
    def test_clean_code_approved(self):
        orch = ReviewOrchestrator(threshold=7)
        ops = [MockOp(content=CLEAN_CODE)]
        result = orch.review(ops)
        assert result.approved
        assert result.verdict == Verdict.APPROVED
        assert result.final_score >= 7

    def test_eval_blocked_by_guardrail(self):
        orch = ReviewOrchestrator(threshold=7, strict_guardrails=True)
        ops = [MockOp(content=EVAL_CODE)]
        result = orch.review(ops)
        assert not result.approved
        assert result.verdict == Verdict.GUARDRAIL_BLOCK

    def test_secret_blocked_by_guardrail(self):
        orch = ReviewOrchestrator(threshold=7, strict_guardrails=True)
        ops = [MockOp(content=SECRET_CODE)]
        result = orch.review(ops)
        assert not result.approved
        assert result.verdict == Verdict.GUARDRAIL_BLOCK
        assert result.guardrail_violations >= 1

    def test_low_score_rejected(self):
        orch = ReviewOrchestrator(threshold=9, strict_guardrails=False)
        ops = [MockOp(content=NESTED_LOOP_CODE + BARE_EXCEPT_CODE)]
        result = orch.review(ops)
        assert not result.approved
        assert result.verdict == Verdict.REJECTED

    def test_rounds_recorded(self):
        orch = ReviewOrchestrator(threshold=7)
        ops = [MockOp(content=CLEAN_CODE)]
        result = orch.review(ops)
        assert len(result.rounds) >= 1
        assert result.rounds[0].round_number == 1

    def test_result_to_dict(self):
        orch = ReviewOrchestrator()
        ops = [MockOp(content=CLEAN_CODE)]
        result = orch.review(ops)
        d = result.to_dict()
        assert "verdict" in d
        assert "approved" in d
        assert "finalScore" in d
        assert "rounds" in d


class TestRetryLoop:
    def test_retry_improves_score(self):
        """Simulate Worker fixing issues on retry."""
        orch = ReviewOrchestrator(threshold=9)
        bad_ops = [MockOp(content=NESTED_LOOP_CODE + BARE_EXCEPT_CODE + MUTABLE_DEFAULT_CODE)]

        retry_count = 0

        def retry_fn(feedback: str) -> list:
            nonlocal retry_count
            retry_count += 1
            return [MockOp(content=CLEAN_CODE)]

        result = orch.review_with_retry(bad_ops, retry_fn=retry_fn, max_retries=2)
        assert result.approved
        assert retry_count >= 1
        assert len(result.rounds) >= 2

    def test_retry_exhausted(self):
        """If the Worker never fixes it, all retries are exhausted."""
        orch = ReviewOrchestrator(threshold=10)  # impossibly high

        def retry_fn(feedback: str) -> list:
            return [MockOp(content=NESTED_LOOP_CODE + BARE_EXCEPT_CODE)]

        result = orch.review_with_retry(
            [MockOp(content=NESTED_LOOP_CODE)],
            retry_fn=retry_fn,
            max_retries=2,
        )
        assert not result.approved
        assert result.verdict == Verdict.REJECTED
        assert len(result.rounds) == 3  # initial + 2 retries

    def test_retry_guardrail_block_no_retry(self):
        """Guardrail violations are never retried — immediate block."""
        orch = ReviewOrchestrator(strict_guardrails=True)

        retry_called = False
        def retry_fn(feedback: str) -> list:
            nonlocal retry_called
            retry_called = True
            return []

        result = orch.review_with_retry(
            [MockOp(content=EVAL_CODE)],
            retry_fn=retry_fn,
            max_retries=2,
        )
        assert not result.approved
        assert result.verdict == Verdict.GUARDRAIL_BLOCK
        assert not retry_called

    def test_no_retry_fn(self):
        """Without retry_fn, rejected plans stay rejected."""
        orch = ReviewOrchestrator(threshold=10)
        result = orch.review_with_retry(
            [MockOp(content=NESTED_LOOP_CODE)],
            retry_fn=None,
            max_retries=2,
        )
        assert not result.approved
        assert len(result.rounds) == 1

    def test_retry_feedback_contains_violations(self):
        """Feedback passed to Worker should describe the issues."""
        orch = ReviewOrchestrator(threshold=10)
        bad_ops = [MockOp(content=BARE_EXCEPT_CODE)]

        captured_feedback = []
        def retry_fn(feedback: str) -> list:
            captured_feedback.append(feedback)
            return [MockOp(content=CLEAN_CODE)]

        orch.review_with_retry(bad_ops, retry_fn=retry_fn)
        assert len(captured_feedback) >= 1
        assert "BP-001" in captured_feedback[0]

    def test_round_to_dict(self):
        orch = ReviewOrchestrator()
        result = orch.review([MockOp(content=CLEAN_CODE)])
        d = result.rounds[0].to_dict()
        assert "round" in d
        assert "verdict" in d
        assert "criticScore" in d


# ═══════════════════════════════════════════════════════════════════════════
# API tests
# ═══════════════════════════════════════════════════════════════════════════

class TestQualityAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        from fastapi.testclient import TestClient
        from code4u.interfaces.api.app import app
        self.client = TestClient(app)
        yield

    def test_review_endpoint_clean(self):
        resp = self.client.post("/api/v1/quality/review", json={
            "content": CLEAN_CODE,
            "filePath": "utils.py",
        })
        assert resp.status_code == 200
        review = resp.json()["review"]
        assert review["passed"]
        assert review["score"] >= 7

    def test_review_endpoint_with_issues(self):
        resp = self.client.post("/api/v1/quality/review", json={
            "content": EVAL_CODE,
            "filePath": "test.py",
        })
        assert resp.status_code == 200
        review = resp.json()["review"]
        assert not review["passed"]
        assert review["criticalCount"] >= 1

    def test_guardrails_endpoint_clean(self):
        resp = self.client.post("/api/v1/quality/guardrails", json={
            "content": CLEAN_CODE,
        })
        assert resp.status_code == 200
        assert resp.json()["result"]["passed"]

    def test_guardrails_endpoint_violation(self):
        resp = self.client.post("/api/v1/quality/guardrails", json={
            "content": EVAL_CODE,
        })
        assert resp.status_code == 200
        assert not resp.json()["result"]["passed"]

    def test_consensus_endpoint_approved(self):
        resp = self.client.post("/api/v1/quality/consensus", json={
            "operations": [{"content": CLEAN_CODE, "filePath": "utils.py", "action": "edit"}],
            "threshold": 7,
            "strictGuardrails": False,
        })
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["approved"]

    def test_consensus_endpoint_blocked(self):
        resp = self.client.post("/api/v1/quality/consensus", json={
            "operations": [{"content": SECRET_CODE, "filePath": "config.py", "action": "edit"}],
            "strictGuardrails": True,
        })
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert not result["approved"]
        assert result["verdict"] == "guardrail_block"

    def test_plan_review_endpoint(self):
        resp = self.client.post("/api/v1/quality/plan-review", json={
            "operations": [
                {"content": CLEAN_CODE, "filePath": "a.py", "action": "edit"},
                {"content": EVAL_CODE, "filePath": "b.py", "action": "edit"},
            ],
            "threshold": 7,
        })
        assert resp.status_code == 200
        assert not resp.json()["review"]["passed"]
