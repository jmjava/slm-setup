"""Fitness function: a skipped behavior layer is not a pass.

EvalResult.passed requires transport, format, structure, and behavior to be
pass. first_failure treats a skipped structure or behavior layer as a failure.
That boundary is in src/local_coding_slm/eval/score.py.
"""

from __future__ import annotations

from local_coding_slm.eval.score import EvalResult, LayerResult


def test_skipped_behavior_layer_is_not_a_pass() -> None:
    result = EvalResult(
        case_id="fitness-skip-behavior",
        layers=(
            LayerResult("transport", "pass", "ok"),
            LayerResult("format", "pass", "ok"),
            LayerResult("structure", "pass", "ok"),
            LayerResult("behavior", "skip", "not executed"),
        ),
    )
    assert result.passed is False
    failure = result.first_failure
    assert failure is not None
    assert failure.name == "behavior"
    assert failure.status == "skip"
