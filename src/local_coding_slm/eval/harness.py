"""Closed-loop measurement harness: MCP tool call → score → retry/escalate."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from local_coding_slm.eval.cases import CASES, EvalCase
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
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    selected = [
        case
        for case in CASES
        if case_ids is None or case.id in case_ids
    ]
    if not selected:
        raise ValueError("no cases selected")
    if repeat < 1:
        raise ValueError("repeat must be >= 1")

    stub_cm = None
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    if backend == "stub":
        from local_coding_slm.eval.stub_ollama import StubOllama

        stub_cm = StubOllama(profile=profile, fast_ms=fast_ms, strong_ms=strong_ms)
        stub = stub_cm.__enter__()
        env["OLLAMA_BASE_URL"] = stub.base_url
    elif backend == "live":
        if base_url:
            env["OLLAMA_BASE_URL"] = base_url
        profile = "live"
    else:
        raise ValueError("backend must be 'stub' or 'live'")

    src = ROOT / "src"
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(src / "local_coding_slm" / "server.py")],
        env=env,
        cwd=str(ROOT),
    )
    rows: list[AttemptRecord] = []
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                for repeat_i in range(repeat):
                    for case in selected:
                        job = f"{case.id}#{repeat_i + 1}"
                        rows.extend(
                            await _run_case(
                                session,
                                case,
                                job=job,
                                backend=backend,
                                profile=profile,
                            )
                        )
    finally:
        if stub_cm is not None:
            stub_cm.__exit__(None, None, None)
    return rows


async def _run_case(
    session: object,
    case: EvalCase,
    *,
    job: str,
    backend: str,
    profile: str,
) -> list[AttemptRecord]:
    rows: list[AttemptRecord] = []
    while True:
        plan = next_plan(case, rows)
        if plan is None:
            return rows
        record = await _one_attempt(
            session, case, plan, backend, profile, job, len(rows) + 1
        )
        rows.append(record)


async def _one_attempt(
    session: object,
    case: EvalCase,
    plan: AttemptPlan,
    backend: str,
    profile: str,
    job: str,
    attempt: int,
) -> AttemptRecord:
    task = case.task if not plan.suffix else f"{case.task}\n\n{plan.suffix}"
    payload = {
        "task": task,
        "files": list(case.files),
        "language": case.language,
        "model": plan.model,
        "max_tokens": 700,
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
    return AttemptRecord(
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
