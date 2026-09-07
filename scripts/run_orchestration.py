#!/usr/bin/env python3
"""Print the scripted routing + review contract. No GPU, no premium API."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from local_coding_slm.eval.cases import (  # noqa: E402
    CASES_BY_ID,
    GOLDEN_FOR_CASE,
    TEST_ADD_SHAPE_ONLY,
    WHITESPACE_GOLDEN,
    WHITESPACE_NO_FENCE,
)
from local_coding_slm.eval.orchestrate import OrchestrationJob, run_job  # noqa: E402
from local_coding_slm.eval.review import accept, reject, rewrite  # noqa: E402
from local_coding_slm.eval.routing import RouteSignals, mechanical_signals  # noqa: E402

REWRITE = "```python\n# user_text.py\n# premium rewrite\n```\n"

JOBS = (
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
        id="keep_ambiguous",
        signals=RouteSignals(),
        premium_keep_text="premium clarifying questions",
    ),
    OrchestrationJob(
        id="delegate_accept",
        signals=mechanical_signals(),
        eval_case=CASES_BY_ID["whitespace_extract"],
        local_replies=(WHITESPACE_GOLDEN,),
        review=accept(),
    ),
    OrchestrationJob(
        id="delegate_repair_then_accept",
        signals=mechanical_signals(),
        eval_case=CASES_BY_ID["whitespace_extract"],
        local_replies=(WHITESPACE_NO_FENCE, WHITESPACE_GOLDEN),
        review=accept(),
    ),
    OrchestrationJob(
        id="delegate_escalate_then_accept",
        signals=mechanical_signals(),
        eval_case=CASES_BY_ID["test_add_execute"],
        local_replies=(TEST_ADD_SHAPE_ONLY, GOLDEN_FOR_CASE["test_add_execute"]),
        review=accept(),
    ),
    OrchestrationJob(
        id="delegate_reject",
        signals=mechanical_signals(security_sensitive=True),
        eval_case=CASES_BY_ID["whitespace_extract"],
        local_replies=(WHITESPACE_GOLDEN,),
        review=reject(notes="auth"),
    ),
    OrchestrationJob(
        id="delegate_rewrite",
        signals=mechanical_signals(),
        eval_case=CASES_BY_ID["whitespace_extract"],
        local_replies=(WHITESPACE_GOLDEN,),
        review=rewrite(REWRITE),
    ),
)


def main() -> None:
    rows = []
    for job in JOBS:
        result = run_job(job)
        row = {k: v for k, v in asdict(result).items() if k != "applied_text"}
        rows.append(row)
        mark = "APPLY" if result.applied else "HOLD"
        print(
            f"{mark} {result.job:32} delegated={str(result.delegated):5} "
            f"route={result.route_reason:28} outcome={result.outcome:18} "
            f"source={result.apply_source or '-':8} "
            f"models={list(result.local_models) or '-'}"
        )
    print(json.dumps({"jobs": len(rows), "applied": sum(1 for r in rows if r["applied"])}))


if __name__ == "__main__":
    main()
