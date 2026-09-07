"""Premium-agent retry policy for delegated local_* work.

Fast first. One same-model repair: format reminder or structure reminder.
Behavior or transport failure escalates to strong. Max three attempts.
A repair success is pass-at-2, never pass-at-1.
"""

from __future__ import annotations

from dataclasses import dataclass

from local_coding_slm.eval.record import AttemptRecord
from local_coding_slm.eval.score import EvalCase

MAX_ATTEMPTS = 3

FORMAT_SUFFIX = (
    "Return only markdown fenced files with path comments. "
    "No prose before or after the fences."
)
STRUCTURE_SUFFIX = (
    "Helpers must be module-level (top-level), not nested. "
    "Keep the public function signatures. Include every required path."
)


@dataclass(frozen=True)
class AttemptPlan:
    model: str
    suffix: str


def next_plan(case: EvalCase, attempts: list[AttemptRecord]) -> AttemptPlan | None:
    """Return the next local_* call, or None if the case is done."""
    del case
    if attempts and attempts[-1].passed:
        return None
    if len(attempts) >= MAX_ATTEMPTS:
        return None
    if not attempts:
        return AttemptPlan(model="fast", suffix="")
    last = attempts[-1]
    if last.model == "fast" and not _repaired_fast(attempts):
        if last.first_failure == "format":
            return AttemptPlan(model="fast", suffix=FORMAT_SUFFIX)
        if last.first_failure == "structure":
            return AttemptPlan(model="fast", suffix=STRUCTURE_SUFFIX)
        return AttemptPlan(model="strong", suffix="")
    if last.model == "fast":
        return AttemptPlan(model="strong", suffix="")
    return None


def _repaired_fast(attempts: list[AttemptRecord]) -> bool:
    return any(row.model == "fast" and row.suffix for row in attempts)
