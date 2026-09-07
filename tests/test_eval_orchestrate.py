"""Premium routing, local failover, and apply-gate tests. No GPU, no live LLM."""

from __future__ import annotations

import unittest

from local_coding_slm.eval.cases import (
    CASES_BY_ID,
    GOLDEN_FOR_CASE,
    TEST_ADD_SHAPE_ONLY,
    WHITESPACE_GOLDEN,
    WHITESPACE_NO_FENCE,
)
from local_coding_slm.eval.orchestrate import (
    ApplyDecision,
    LocalAttempt,
    OrchestrationJob,
    ScriptedLocal,
    decide_apply,
    run_job,
)
from local_coding_slm.eval.policy import FORMAT_SUFFIX
from local_coding_slm.eval.record import AttemptRecord
from local_coding_slm.eval.review import (
    LOCAL_REVIEW_TOOL,
    PREMIUM_REVIEWER,
    ReviewVerdict,
    accept,
    reject,
    rewrite,
)
from local_coding_slm.eval.routing import RouteSignals, mechanical_signals, route


def _attempt(*, passed: bool, text: str = "LOCAL") -> LocalAttempt:
    record = AttemptRecord(
        job="j",
        case_id="whitespace_extract",
        attempt=1,
        model="fast",
        suffix="",
        passed=passed,
        first_failure=None if passed else "behavior",
        mcp_ms=0.0,
        score_ms=0.0,
        elapsed_ms=0.0,
        response_chars=len(text),
        backend="script",
        profile="test",
        layers={},
    )
    return LocalAttempt(record=record, text=text)


class RouteTests(unittest.TestCase):
    def test_mechanical_delegates_and_requires_review(self) -> None:
        decision = route(mechanical_signals())
        self.assertEqual(decision.action, "delegate")
        self.assertEqual(decision.reason, "mechanical")
        self.assertTrue(decision.requires_premium_review)

    def test_security_sensitive_mechanical_still_delegates_with_review(self) -> None:
        decision = route(mechanical_signals(security_sensitive=True))
        self.assertEqual(decision.action, "delegate")
        self.assertEqual(decision.reason, "mechanical_security_sensitive")
        self.assertTrue(decision.requires_premium_review)

    def test_do_not_delegate_flags_win(self) -> None:
        cases = (
            ("incident_debug", mechanical_signals(incident_debug=True)),
            ("architectural", mechanical_signals(architectural=True)),
            ("needs_live_tools", mechanical_signals(needs_live_tools=True)),
        )
        for reason, signals in cases:
            with self.subTest(reason=reason):
                decision = route(signals)
                self.assertEqual(decision.action, "keep")
                self.assertEqual(decision.reason, reason)
                self.assertFalse(decision.requires_premium_review)

    def test_ambiguous_stays_on_premium(self) -> None:
        decision = route(RouteSignals(shape_obvious=False, context_fits=True))
        self.assertEqual(decision.action, "keep")
        self.assertEqual(decision.reason, "not_mechanical")


class ApplyGateTests(unittest.TestCase):
    def test_keep_does_not_need_review(self) -> None:
        applied = decide_apply(
            delegated=False,
            last=None,
            verdict=None,
            keep_text="premium wrote this",
        )
        self.assertEqual(
            applied,
            ApplyDecision(
                "kept_on_premium", True, "premium", "premium wrote this"
            ),
        )

    def test_delegated_without_review_cannot_apply(self) -> None:
        applied = decide_apply(
            delegated=True,
            last=_attempt(passed=True),
            verdict=None,
        )
        self.assertFalse(applied.applied)
        self.assertEqual(applied.blocked, "no_review")

    def test_local_review_tool_cannot_approve(self) -> None:
        applied = decide_apply(
            delegated=True,
            last=_attempt(passed=True),
            verdict=ReviewVerdict(
                decision="accept",
                reviewer=LOCAL_REVIEW_TOOL,
            ),
        )
        self.assertFalse(applied.applied)
        self.assertEqual(applied.blocked, "local_review_is_not_approval")

    def test_reject_drops_passing_local(self) -> None:
        applied = decide_apply(
            delegated=True,
            last=_attempt(passed=True, text="SECRET_PATCH"),
            verdict=reject(notes="auth handling is wrong"),
        )
        self.assertEqual(applied.outcome, "rejected")
        self.assertFalse(applied.applied)
        self.assertIsNone(applied.text)

    def test_rewrite_applies_premium_text_not_local(self) -> None:
        applied = decide_apply(
            delegated=True,
            last=_attempt(passed=True, text="LOCAL_PATCH"),
            verdict=rewrite("PREMIUM_REWRITE"),
        )
        self.assertEqual(applied.outcome, "applied_rewrite")
        self.assertTrue(applied.applied)
        self.assertEqual(applied.source, "premium")
        self.assertEqual(applied.text, "PREMIUM_REWRITE")

    def test_accept_applies_local_only_when_layers_passed(self) -> None:
        ok = decide_apply(
            delegated=True,
            last=_attempt(passed=True, text="LOCAL_PATCH"),
            verdict=accept(),
        )
        self.assertEqual(ok.outcome, "applied_local")
        self.assertEqual(ok.source, "local")
        self.assertEqual(ok.text, "LOCAL_PATCH")
        blocked = decide_apply(
            delegated=True,
            last=_attempt(passed=False, text="BAD"),
            verdict=accept(),
        )
        self.assertFalse(blocked.applied)
        self.assertEqual(blocked.blocked, "accept_unproven_local")


class OrchestratorLoopTests(unittest.TestCase):
    def test_keep_never_calls_local(self) -> None:
        def boom(plan: object) -> str:
            raise AssertionError(f"local must not run for keep jobs: {plan}")

        result = run_job(
            OrchestrationJob(
                id="auth_incident",
                signals=mechanical_signals(incident_debug=True),
                premium_keep_text="premium debug patch",
            ),
            generate=boom,
        )
        self.assertFalse(result.delegated)
        self.assertEqual(result.outcome, "kept_on_premium")
        self.assertEqual(result.apply_source, "premium")
        self.assertEqual(result.applied_text, "premium debug patch")
        self.assertEqual(result.local_attempts, 0)
        self.assertIsNone(result.review_decision)

    def test_architectural_and_live_tools_also_keep(self) -> None:
        for job_id, signals in (
            ("split_service", mechanical_signals(architectural=True)),
            ("needs_search", mechanical_signals(needs_live_tools=True)),
            ("vague", RouteSignals()),
        ):
            with self.subTest(job_id=job_id):
                result = run_job(OrchestrationJob(id=job_id, signals=signals))
                self.assertFalse(result.delegated)
                self.assertEqual(result.local_attempts, 0)

    def test_mechanical_fast_accept(self) -> None:
        local = ScriptedLocal([WHITESPACE_GOLDEN])
        reviewer_calls: list[tuple[str, bool]] = []

        def reviewer(job_id: str, text: str, passed: bool) -> ReviewVerdict:
            reviewer_calls.append((job_id, passed))
            self.assertIn("_normalize_whitespace", text)
            return accept(notes="ok")

        result = run_job(
            OrchestrationJob(
                id="extract_ok",
                signals=mechanical_signals(),
                eval_case=CASES_BY_ID["whitespace_extract"],
            ),
            generate=local,
            reviewer=reviewer,
        )
        self.assertTrue(result.delegated)
        self.assertEqual(result.local_models, ("fast",))
        self.assertTrue(result.local_passed)
        self.assertEqual(result.outcome, "applied_local")
        self.assertEqual(result.apply_source, "local")
        self.assertEqual(result.applied_text, WHITESPACE_GOLDEN)
        self.assertEqual(result.review_reviewer, PREMIUM_REVIEWER)
        self.assertEqual(reviewer_calls, [("extract_ok", True)])
        self.assertEqual(len(local.calls), 1)

    def test_format_fail_repairs_on_fast_then_premium_accepts(self) -> None:
        local = ScriptedLocal([WHITESPACE_NO_FENCE, WHITESPACE_GOLDEN])
        result = run_job(
            OrchestrationJob(
                id="extract_repair",
                signals=mechanical_signals(),
                eval_case=CASES_BY_ID["whitespace_extract"],
                review=accept(),
            ),
            generate=local,
        )
        self.assertEqual(result.local_models, ("fast", "fast"))
        self.assertTrue(result.local_suffixes[1])
        self.assertIn("fenced", result.local_suffixes[1])
        self.assertEqual(local.calls[1].suffix, FORMAT_SUFFIX)
        self.assertEqual(result.outcome, "applied_local")
        self.assertTrue(result.applied)

    def test_behavior_fail_escalates_to_strong_then_review(self) -> None:
        golden = GOLDEN_FOR_CASE["test_add_execute"]
        local = ScriptedLocal([TEST_ADD_SHAPE_ONLY, golden])
        result = run_job(
            OrchestrationJob(
                id="tests_escalate",
                signals=mechanical_signals(),
                eval_case=CASES_BY_ID["test_add_execute"],
                review=accept(),
            ),
            generate=local,
        )
        self.assertEqual(result.local_models, ("fast", "strong"))
        self.assertTrue(result.local_passed)
        self.assertEqual(result.outcome, "applied_local")
        self.assertEqual(result.apply_source, "local")

    def test_premium_rejects_passing_local(self) -> None:
        result = run_job(
            OrchestrationJob(
                id="insecure_helper",
                signals=mechanical_signals(security_sensitive=True),
                eval_case=CASES_BY_ID["whitespace_extract"],
                local_replies=(WHITESPACE_GOLDEN,),
                review=reject(notes="do not apply until auth is reviewed"),
            )
        )
        self.assertTrue(result.delegated)
        self.assertEqual(result.route_reason, "mechanical_security_sensitive")
        self.assertTrue(result.local_passed)
        self.assertEqual(result.outcome, "rejected")
        self.assertFalse(result.applied)
        self.assertIsNone(result.applied_text)

    def test_premium_rewrite_not_raw_local(self) -> None:
        rewritten = "```python\n# user_text.py\n# premium rewrite\n```\n"
        result = run_job(
            OrchestrationJob(
                id="trim_extract",
                signals=mechanical_signals(),
                eval_case=CASES_BY_ID["whitespace_extract"],
                local_replies=(WHITESPACE_GOLDEN,),
                review=rewrite(rewritten, notes="trimmed"),
            )
        )
        self.assertEqual(result.outcome, "applied_rewrite")
        self.assertEqual(result.apply_source, "premium")
        self.assertEqual(result.applied_text, rewritten)
        self.assertNotEqual(result.applied_text, WHITESPACE_GOLDEN)

    def test_missing_review_blocks_even_after_local_pass(self) -> None:
        result = run_job(
            OrchestrationJob(
                id="forgot_review",
                signals=mechanical_signals(),
                eval_case=CASES_BY_ID["whitespace_extract"],
                local_replies=(WHITESPACE_GOLDEN,),
                review=None,
            )
        )
        self.assertTrue(result.local_passed)
        self.assertFalse(result.applied)
        self.assertEqual(result.blocked, "no_review")
        self.assertEqual(result.outcome, "blocked")


if __name__ == "__main__":
    unittest.main()
