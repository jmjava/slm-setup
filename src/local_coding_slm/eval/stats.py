"""Stratified summary for harness JSON. Looks up tool/category from the corpus."""

from __future__ import annotations

from collections import defaultdict

from local_coding_slm.eval.record import AttemptRecord, summarize
from local_coding_slm.eval.taxonomy import category_of


def enrich_summary(rows: list[AttemptRecord]) -> dict[str, object]:
    """Add by_tool and by_category rates. Same pass@1 / pass@end rules as summarize."""
    stats = summarize(rows)
    by_job: dict[str, list[AttemptRecord]] = {}
    for row in rows:
        by_job.setdefault(row.job, []).append(row)

    def _group(key_fn) -> dict[str, dict[str, object]]:
        buckets: dict[str, list[str]] = defaultdict(list)
        for job, group in by_job.items():
            buckets[key_fn(group[0])].append(job)
        out: dict[str, dict[str, object]] = {}
        for key, jobs in sorted(buckets.items()):
            groups = [by_job[job] for job in jobs]
            n = len(groups)
            pass_at_1 = sum(1 for g in groups if any(r.passed and r.attempt == 1 for r in g))
            pass_end = sum(1 for g in groups if any(r.passed for r in g))
            escalated = sum(1 for g in groups if any(r.model == "strong" for r in g))
            fails: dict[str, int] = {}
            for group in groups:
                for row in group:
                    if row.first_failure:
                        fails[row.first_failure] = fails.get(row.first_failure, 0) + 1
            out[key] = {
                "cases": n,
                "pass_at_1": pass_at_1 / n if n else 0.0,
                "pass_end": pass_end / n if n else 0.0,
                "escalated": escalated / n if n else 0.0,
                "first_failure": fails,
            }
        return out

    from local_coding_slm.eval.cases import CASES_BY_ID

    stats["by_tool"] = _group(lambda row: CASES_BY_ID[row.case_id].tool)
    stats["by_category"] = _group(lambda row: category_of(row.case_id))
    return stats
