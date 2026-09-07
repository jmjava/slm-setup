"""Premium orchestrator loop: route → local fast/strong → review → apply.

This is the missing half of the harness. ``policy.next_plan`` is local
failover after a task was already delegated. This module decides whether
to delegate, then refuses to apply until a premium verdict exists.

No Cursor / GPT / Claude API is called. Tests inject a scripted local
worker and a scripted reviewer.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from local_coding_slm.eval.policy import AttemptPlan, next_plan
from local_coding_slm.eval.record import AttemptRecord
from local_coding_slm.eval.review import (
    LOCAL_REVIEW_TOOL,
    ReviewPacket,
    ReviewVerdict,
    ScriptedReviewer,
    is_premium_review,
)
from local_coding_slm.eval.routing import RouteDecision, RouteSignals, route
from local_coding_slm.eval.score import EvalCase, EvalResult, score_candidate

GenerateFn = Callable[[AttemptPlan], str]
ReviewFn = Callable[..., ReviewVerdict | None]


@dataclass(frozen=True)
class LocalAttempt:
    record: AttemptRecord
    text: str
    scored: EvalResult | None = None

    @property
    def passed(self) -> bool:
        return self.record.passed


@dataclass(frozen=True)
class ApplyDecision:
    outcome: str
    applied: bool
    source: str | None
    text: str | None
    blocked: str | None = None


@dataclass(frozen=True)
class OrchestrationJob:
    id: str
    signals: RouteSignals
    eval_case: EvalCase | None = None
    local_replies: tuple[str, ...] = ()
    review: ReviewVerdict | None = None
    premium_keep_text: str = ""
    local_review_notes: str = ""


@dataclass(frozen=True)
class JobResult:
    job: str
    case_id: str
    delegated: bool
    route_reason: str
    outcome: str
    applied: bool
    apply_source: str | None
    applied_text: str | None
    blocked: str | None
    local_models: tuple[str, ...]
    local_suffixes: tuple[str, ...]
    local_attempts: int
    review_decision: str | None
    review_reviewer: str | None
    local_passed: bool | None
    local_review_notes: str = ""


class ScriptedLocal:
    """Queue of candidate strings. Records every plan the policy requested."""

    def __init__(self, replies: tuple[str, ...] | list[str]) -> None:
        self._replies = list(replies)
        self.calls: list[AttemptPlan] = []

    def __call__(self, plan: AttemptPlan) -> str:
        self.calls.append(plan)
        if not self._replies:
            raise AssertionError("local worker called with no remaining replies")
        return self._replies.pop(0)


def decide_apply(
    *,
    delegated: bool,
    last: LocalAttempt | None,
    verdict: ReviewVerdict | None,
    keep_text: str = "",
    eval_case: EvalCase | None = None,
) -> ApplyDecision:
    """Apply gate. Local layer-pass is not approval. Rewrites are re-scored."""
    if not delegated:
        return ApplyDecision(
            outcome="kept_on_premium",
            applied=True,
            source="premium",
            text=keep_text,
        )
    if not is_premium_review(verdict):
        blocked = "no_review" if verdict is None else "not_premium_review"
        if verdict is not None and verdict.reviewer == LOCAL_REVIEW_TOOL:
            blocked = "local_review_is_not_approval"
        return ApplyDecision(
            outcome="blocked",
            applied=False,
            source=None,
            text=None,
            blocked=blocked,
        )
    assert verdict is not None
    if verdict.decision == "reject":
        return ApplyDecision(
            outcome="rejected",
            applied=False,
            source=None,
            text=None,
        )
    if verdict.decision == "rewrite":
        if not verdict.text.strip():
            return ApplyDecision(
                outcome="blocked",
                applied=False,
                source=None,
                text=None,
                blocked="empty_rewrite",
            )
        if eval_case is not None:
            scored = score_candidate(verdict.text, eval_case)
            if not scored.passed:
                fail = scored.first_failure
                layer = fail.name if fail is not None else "behavior"
                return ApplyDecision(
                    outcome="blocked",
                    applied=False,
                    source=None,
                    text=None,
                    blocked=f"rewrite_unproven:{layer}",
                )
        return ApplyDecision(
            outcome="applied_rewrite",
            applied=True,
            source="premium",
            text=verdict.text,
        )
    if last is None or not last.passed:
        return ApplyDecision(
            outcome="blocked",
            applied=False,
            source=None,
            text=None,
            blocked="accept_unproven_local",
        )
    return ApplyDecision(
        outcome="applied_local",
        applied=True,
        source="local",
        text=last.text,
    )


def run_local_loop(
    case: EvalCase,
    generate: GenerateFn,
    *,
    job: str,
) -> list[LocalAttempt]:
    """Fast → repair → strong, same policy as the MCP harness."""
    attempts: list[LocalAttempt] = []
    records: list[AttemptRecord] = []
    while True:
        plan = next_plan(case, records)
        if plan is None:
            return attempts
        text = generate(plan)
        scored = score_candidate(text, case)
        fail = scored.first_failure
        record = AttemptRecord(
            job=job,
            case_id=case.id,
            attempt=len(records) + 1,
            model=plan.model,
            suffix=plan.suffix,
            passed=scored.passed,
            first_failure=None if fail is None else fail.name,
            mcp_ms=0.0,
            score_ms=0.0,
            elapsed_ms=0.0,
            response_chars=len(text),
            backend="script",
            profile="orchestrator",
            layers={item.name: item.status for item in scored.layers},
        )
        records.append(record)
        attempts.append(LocalAttempt(record=record, text=text, scored=scored))


def finish_delegated_job(
    job: OrchestrationJob,
    attempts: list[LocalAttempt],
    verdict: ReviewVerdict | None,
) -> JobResult:
    """Apply gate after local attempts (scripted or MCP) already ran."""
    files = job.eval_case.files if job.eval_case is not None else ()
    decision = route(job.signals, files)
    if decision.action != "delegate":
        raise ValueError(f"{job.id}: finish_delegated_job requires a delegated route")
    last = attempts[-1] if attempts else None
    apply = decide_apply(
        delegated=True,
        last=last,
        verdict=verdict,
        eval_case=job.eval_case,
    )
    return _result(job, decision, apply, attempts, verdict)


def run_job(
    job: OrchestrationJob,
    *,
    generate: GenerateFn | None = None,
    reviewer: ReviewFn | ScriptedReviewer | None = None,
) -> JobResult:
    files = job.eval_case.files if job.eval_case is not None else ()
    decision: RouteDecision = route(job.signals, files)
    if decision.action == "keep":
        apply = decide_apply(
            delegated=False,
            last=None,
            verdict=None,
            keep_text=job.premium_keep_text,
        )
        return _result(
            job,
            decision,
            apply,
            attempts=[],
            verdict=None,
        )

    if job.eval_case is None:
        raise ValueError(f"{job.id}: delegated jobs need an eval_case")

    local = generate if generate is not None else ScriptedLocal(job.local_replies)
    scripted: ScriptedReviewer | None = None
    if reviewer is None:
        scripted = ScriptedReviewer(job.review)
        review_fn: ReviewFn = scripted.review_packet
    elif isinstance(reviewer, ScriptedReviewer):
        review_fn = reviewer.review_packet
    else:
        review_fn = reviewer

    attempts = run_local_loop(job.eval_case, local, job=job.id)
    last = attempts[-1] if attempts else None
    packet = _packet_for(job, last)
    verdict = _invoke_review(review_fn, packet)
    apply = decide_apply(
        delegated=True,
        last=last,
        verdict=verdict,
        eval_case=job.eval_case,
    )
    return _result(job, decision, apply, attempts, verdict)


def _packet_for(job: OrchestrationJob, last: LocalAttempt | None) -> ReviewPacket:
    layers = dict(last.record.layers) if last is not None else {}
    return ReviewPacket(
        job_id=job.id,
        local_text=last.text if last is not None else "",
        passed=last.passed if last is not None else False,
        layers=layers,
        first_failure=None if last is None else last.record.first_failure,
        local_review_notes=job.local_review_notes,
        case_id=job.eval_case.id if job.eval_case is not None else job.id,
    )


def _invoke_review(review_fn: ReviewFn, packet: ReviewPacket) -> ReviewVerdict | None:
    try:
        return review_fn(packet)
    except TypeError:
        return review_fn(packet.job_id, packet.local_text, packet.passed)


def _result(
    job: OrchestrationJob,
    decision: RouteDecision,
    apply: ApplyDecision,
    attempts: list[LocalAttempt],
    verdict: ReviewVerdict | None,
) -> JobResult:
    case_id = job.eval_case.id if job.eval_case is not None else job.id
    last_passed = attempts[-1].passed if attempts else None
    return JobResult(
        job=job.id,
        case_id=case_id,
        delegated=decision.action == "delegate",
        route_reason=decision.reason,
        outcome=apply.outcome,
        applied=apply.applied,
        apply_source=apply.source,
        applied_text=apply.text,
        blocked=apply.blocked,
        local_models=tuple(item.record.model for item in attempts),
        local_suffixes=tuple(item.record.suffix for item in attempts),
        local_attempts=len(attempts),
        review_decision=None if verdict is None else verdict.decision,
        review_reviewer=None if verdict is None else verdict.reviewer,
        local_passed=last_passed,
        local_review_notes=job.local_review_notes,
    )
