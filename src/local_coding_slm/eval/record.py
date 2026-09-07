"""One measured attempt and a run summary. No hostnames or raw model dumps."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from statistics import median


@dataclass(frozen=True)
class AttemptRecord:
    job: str
    case_id: str
    attempt: int
    model: str
    suffix: str
    passed: bool
    first_failure: str | None
    mcp_ms: float
    score_ms: float
    elapsed_ms: float
    response_chars: int
    backend: str
    profile: str
    layers: dict[str, str]


@dataclass
class CaseOutcome:
    job: str
    case_id: str
    pass_at: int | None
    escalated: bool
    exhausted: bool
    attempts: int
    elapsed_ms: float


def outcome_for_case(job: str, case_id: str, rows: list[AttemptRecord]) -> CaseOutcome:
    passed = [row for row in rows if row.passed]
    escalated = any(row.model == "strong" for row in rows)
    pass_at = passed[0].attempt if passed else None
    return CaseOutcome(
        job=job,
        case_id=case_id,
        pass_at=pass_at,
        escalated=escalated,
        exhausted=pass_at is None,
        attempts=len(rows),
        elapsed_ms=sum(row.elapsed_ms for row in rows),
    )


def summarize(rows: list[AttemptRecord]) -> dict[str, object]:
    by_job: dict[str, list[AttemptRecord]] = {}
    for row in rows:
        by_job.setdefault(row.job, []).append(row)
    outcomes = [
        outcome_for_case(job, group[0].case_id, group)
        for job, group in sorted(by_job.items())
    ]
    n = len(outcomes)
    pass_at_1 = sum(1 for item in outcomes if item.pass_at == 1)
    pass_end = sum(1 for item in outcomes if item.pass_at is not None)
    latencies = [row.mcp_ms for row in rows]
    fail_hist: dict[str, int] = {}
    for row in rows:
        if row.first_failure:
            fail_hist[row.first_failure] = fail_hist.get(row.first_failure, 0) + 1
    return {
        "cases": n,
        "attempts": len(rows),
        "pass_at_1": pass_at_1 / n if n else 0.0,
        "pass_end": pass_end / n if n else 0.0,
        "escalated": sum(1 for item in outcomes if item.escalated) / n if n else 0.0,
        "mcp_ms_p50": median(latencies) if latencies else 0.0,
        "mcp_ms_max": max(latencies) if latencies else 0.0,
        "first_failure": fail_hist,
        "cases_detail": [asdict(item) for item in outcomes],
    }


def write_jsonl(path: str, rows: list[AttemptRecord]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(asdict(row), sort_keys=True) + "\n")
