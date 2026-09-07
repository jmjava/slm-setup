"""Scripted premium jobs for the MCP + apply-gate loop."""

from __future__ import annotations

from local_coding_slm.eval.cases import CASES_BY_ID
from local_coding_slm.eval.orchestrate import OrchestrationJob
from local_coding_slm.eval.review import accept, reject, rewrite
from local_coding_slm.eval.routing import RouteSignals, mechanical_signals

REWRITE_CLAMP = '''\
```python
# clamp.py
def clamp(value: int, lo: int, hi: int) -> int:
    if lo > hi:
        lo, hi = hi, lo
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value
```
'''

MCP_JOBS: tuple[OrchestrationJob, ...] = (
    OrchestrationJob(
        id="keep_incident",
        signals=mechanical_signals(incident_debug=True),
        premium_keep_text="premium incident patch",
    ),
    OrchestrationJob(
        id="keep_architecture",
        signals=mechanical_signals(architectural=True),
        premium_keep_text="premium architecture patch",
    ),
    OrchestrationJob(
        id="keep_live_tools",
        signals=mechanical_signals(needs_live_tools=True),
        premium_keep_text="premium uses repo search",
    ),
    OrchestrationJob(
        id="keep_ambiguous",
        signals=RouteSignals(),
        premium_keep_text="premium clarifying questions",
    ),
    OrchestrationJob(
        id="mcp_extract_accept",
        signals=mechanical_signals(),
        eval_case=CASES_BY_ID["whitespace_extract"],
        review=accept(notes="layers passed; apply local extract"),
    ),
    OrchestrationJob(
        id="mcp_move_accept",
        signals=mechanical_signals(),
        eval_case=CASES_BY_ID["move_function_imports"],
        review=accept(notes="imports updated"),
    ),
    OrchestrationJob(
        id="mcp_parser_accept",
        signals=mechanical_signals(),
        eval_case=CASES_BY_ID["extract_shared_parser"],
        review=accept(),
    ),
    OrchestrationJob(
        id="mcp_pipeline_accept",
        signals=mechanical_signals(),
        eval_case=CASES_BY_ID["split_pipeline"],
        review=accept(),
    ),
    OrchestrationJob(
        id="mcp_tests_accept",
        signals=mechanical_signals(),
        eval_case=CASES_BY_ID["test_add_execute"],
        review=accept(),
    ),
    OrchestrationJob(
        id="mcp_code_rewrite",
        signals=mechanical_signals(),
        eval_case=CASES_BY_ID["implement_clamp"],
        review=rewrite(REWRITE_CLAMP, notes="also swap lo/hi if inverted"),
    ),
    OrchestrationJob(
        id="mcp_explain_accept",
        signals=mechanical_signals(),
        eval_case=CASES_BY_ID["explain_clamp"],
        review=accept(notes="prose is accurate"),
    ),
    OrchestrationJob(
        id="mcp_review_notes_only",
        signals=mechanical_signals(security_sensitive=True),
        eval_case=CASES_BY_ID["review_login"],
        review=reject(notes="local_review notes are not an apply"),
    ),
    OrchestrationJob(
        id="mcp_reject_security",
        signals=mechanical_signals(security_sensitive=True),
        eval_case=CASES_BY_ID["implement_clamp"],
        review=reject(notes="do not apply until bounds are reviewed"),
    ),
)


def job_by_id(job_id: str) -> OrchestrationJob:
    for job in MCP_JOBS:
        if job.id == job_id:
            return job
    raise KeyError(job_id)
