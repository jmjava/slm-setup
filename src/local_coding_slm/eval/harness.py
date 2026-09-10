"""Closed-loop measurement: MCP tool call → score → retry/escalate → apply gate."""

from __future__ import annotations

import os
import sys
import time
from dataclasses import replace
from pathlib import Path

from local_coding_slm.eval.cases import CASES, EvalCase
from local_coding_slm.eval.jobs import MCP_JOBS
from local_coding_slm.eval.orchestrate import (
    JobResult,
    LocalAttempt,
    OrchestrationJob,
    finish_delegated_job,
    run_job,
)
from local_coding_slm.eval.policy import AttemptPlan, next_plan
from local_coding_slm.eval.record import AttemptRecord, summarize
from local_coding_slm.eval.score import score_candidate

ROOT = Path(__file__).resolve().parents[3]


async def run_campaign(
    *,
    backend: str,
    profile: str,
    case_ids: list[str] | None = None,
    repeat: int = 1,
    fast_ms: float = 8.0,
    strong_ms: float = 25.0,
    base_url: str | None = None,
) -> list[AttemptRecord]:
    """Run the corpus through stdio MCP. ``backend=stub`` starts loopback Ollama."""
    rows: list[AttemptRecord] = []

    async def _collect(session: object, backend_name: str, profile_name: str) -> None:
        selected = [
            case
            for case in CASES
            if case_ids is None or case.id in case_ids
        ]
        if not selected:
            raise ValueError("no cases selected")
        if repeat < 1:
            raise ValueError("repeat must be >= 1")
        for repeat_i in range(repeat):
            for case in selected:
                job = f"{case.id}#{repeat_i + 1}"
                attempts = await _run_local_mcp(
                    session,
                    case,
                    job=job,
                    backend=backend_name,
                    profile=profile_name,
                )
                rows.extend(item.record for item in attempts)

    await _with_session(
        backend=backend,
        profile=profile,
        fast_ms=fast_ms,
        strong_ms=strong_ms,
        base_url=base_url,
        body=_collect,
    )
    return rows


async def run_orchestrated_campaign(
    *,
    backend: str,
    profile: str,
    job_ids: list[str] | None = None,
    fast_ms: float = 8.0,
    strong_ms: float = 25.0,
    base_url: str | None = None,
) -> list[JobResult]:
    """Route → MCP local loop → premium apply gate. Stub reviewer, real MCP."""
    results: list[JobResult] = []
    selected = [
        job
        for job in MCP_JOBS
        if job_ids is None or job.id in job_ids
    ]
    if not selected:
        raise ValueError("no orchestration jobs selected")

    async def _collect(session: object, backend_name: str, profile_name: str) -> None:
        for job in selected:
            results.append(
                await _run_orchestrated_job(
                    session,
                    job,
                    backend=backend_name,
                    profile=profile_name,
                )
            )

    await _with_session(
        backend=backend,
        profile=profile,
        fast_ms=fast_ms,
        strong_ms=strong_ms,
        base_url=base_url,
        body=_collect,
    )
    return results


async def _with_session(
    *,
    backend: str,
    profile: str,
    fast_ms: float,
    strong_ms: float,
    base_url: str | None,
    body,
) -> None:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    stub_cm = None
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    profile_name = profile
    if backend == "stub":
        from local_coding_slm.eval.stub_ollama import StubOllama

        stub_cm = StubOllama(profile=profile, fast_ms=fast_ms, strong_ms=strong_ms)
        stub = stub_cm.__enter__()
        env["OLLAMA_BASE_URL"] = stub.base_url
    elif backend == "live":
        if base_url:
            env["OLLAMA_BASE_URL"] = base_url
        profile_name = "live"
    else:
        raise ValueError("backend must be 'stub' or 'live'")

    src = ROOT / "src"
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(src / "local_coding_slm" / "server.py")],
        env=env,
        cwd=str(ROOT),
    )
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                await body(session, backend, profile_name)
    finally:
        if stub_cm is not None:
            stub_cm.__exit__(None, None, None)


async def _run_orchestrated_job(
    session: object,
    job: OrchestrationJob,
    *,
    backend: str,
    profile: str,
) -> JobResult:
    from local_coding_slm.eval.routing import route

    files = job.eval_case.files if job.eval_case is not None else ()
    decision = route(job.signals, files)
    if decision.action == "keep":
        return run_job(job)
    if job.eval_case is None:
        raise ValueError(f"{job.id}: delegated jobs need an eval_case")
    notes = job.local_review_notes
    if job.signals.security_sensitive and not notes:
        notes = await _call_local_review(session, job.eval_case)
        job = replace(job, local_review_notes=notes)
    attempts = await _run_local_mcp(
        session,
        job.eval_case,
        job=job.id,
        backend=backend,
        profile=profile,
    )
    return finish_delegated_job(job, attempts, job.review)


async def _run_local_mcp(
    session: object,
    case: EvalCase,
    *,
    job: str,
    backend: str,
    profile: str,
) -> list[LocalAttempt]:
    attempts: list[LocalAttempt] = []
    records: list[AttemptRecord] = []
    while True:
        plan = next_plan(case, records)
        if plan is None:
            return attempts
        item = await _one_attempt(
            session, case, plan, backend, profile, job, len(records) + 1
        )
        attempts.append(item)
        records.append(item.record)


async def _call_local_review(session: object, case: EvalCase) -> str:
    """Cheap first-pass notes for the premium packet. Not an apply."""
    payload = {
        "task": (
            "First-pass review only. Flag obvious null, auth, secret, and "
            "error-handling gaps. Do not rewrite.\n\nOriginal task:\n"
            + case.task
        ),
        "files": list(case.files),
        "language": case.language,
        "model": "fast",
        "max_tokens": 400,
    }
    tool = await session.call_tool("local_review", payload)  # type: ignore[attr-defined]
    return "".join(
        block.text for block in tool.content if getattr(block, "text", None)
    )


async def _one_attempt(
    session: object,
    case: EvalCase,
    plan: AttemptPlan,
    backend: str,
    profile: str,
    job: str,
    attempt: int,
) -> LocalAttempt:
    task = case.task if not plan.suffix else f"{case.task}\n\n{plan.suffix}"
    payload = {
        "task": task,
        "files": list(case.files),
        "language": case.language,
        "model": plan.model,
        "max_tokens": case.max_tokens,
    }
    if case.style:
        payload["style"] = case.style
    t0 = time.perf_counter()
    tool = await session.call_tool(case.tool, payload)  # type: ignore[attr-defined]
    mcp_ms = (time.perf_counter() - t0) * 1000.0
    text = "".join(
        block.text for block in tool.content if getattr(block, "text", None)
    )
    t1 = time.perf_counter()
    scored = score_candidate(text, case)
    score_ms = (time.perf_counter() - t1) * 1000.0
    fail = scored.first_failure
    record = AttemptRecord(
        job=job,
        case_id=case.id,
        attempt=attempt,
        model=plan.model,
        suffix=plan.suffix,
        passed=scored.passed,
        first_failure=None if fail is None else fail.name,
        mcp_ms=round(mcp_ms, 3),
        score_ms=round(score_ms, 3),
        elapsed_ms=round(mcp_ms + score_ms, 3),
        response_chars=len(text),
        backend=backend,
        profile=profile,
        layers={item.name: item.status for item in scored.layers},
    )
    return LocalAttempt(record=record, text=text, scored=scored)


def campaign_pass_end(rows: list[AttemptRecord]) -> tuple[float, int]:
    stats = summarize(rows)
    return float(stats["pass_end"]), int(stats["cases"])


def orchestrated_pass_end(results: list[JobResult]) -> tuple[float, int]:
    delegated = [item for item in results if item.delegated]
    n = len(delegated)
    if n == 0:
        return 0.0, 0
    passed = sum(1 for item in delegated if item.local_passed)
    return passed / n, n


def harness_exit_code(
    pass_end: float,
    n: int,
    min_pass_end: float = 0.0,
) -> int:
    """Fail-closed: no rows or pass@end of 0 is never success."""
    if n <= 0 or pass_end <= 0.0 or pass_end < min_pass_end:
        return 1
    return 0


def format_summary(rows: list[AttemptRecord]) -> str:
    stats = summarize(rows)
    lines = [
        f"backend={rows[0].backend if rows else '?'} profile={rows[0].profile if rows else '?'}",
        f"cases={stats['cases']} attempts={stats['attempts']}",
        (
            f"pass@1={stats['pass_at_1']:.2f} pass@end={stats['pass_end']:.2f} "
            f"escalated={stats['escalated']:.2f}"
        ),
        f"mcp_ms p50={stats['mcp_ms_p50']:.1f} max={stats['mcp_ms_max']:.1f}",
        f"first_failure={stats['first_failure']}",
    ]
    for item in stats["cases_detail"]:
        lines.append(
            f"  {item['job']}: pass_at={item['pass_at']} "
            f"attempts={item['attempts']} escalated={item['escalated']} "
            f"ms={item['elapsed_ms']:.1f}"
        )
    return "\n".join(lines)


def format_orchestrated(results: list[JobResult]) -> str:
    pass_end, delegated_n = orchestrated_pass_end(results)
    lines = [
        f"jobs={len(results)} applied={sum(1 for item in results if item.applied)} "
        f"delegated={sum(1 for item in results if item.delegated)}",
        f"pass@end={pass_end:.2f} delegated_jobs={delegated_n}",
    ]
    for item in results:
        models = list(item.local_models) or "-"
        lines.append(
            f"  {item.job}: delegated={item.delegated} route={item.route_reason} "
            f"outcome={item.outcome} source={item.apply_source or '-'} "
            f"models={models}"
        )
    return "\n".join(lines)
