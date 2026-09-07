"""A6 acceptance uses the behavior-layer scorer, not a `def test` substring."""

from local_coding_slm.eval.cases import CASES_BY_ID
from local_coding_slm.eval.score import EvalResult, score_candidate


def score_a6(text: str) -> EvalResult:
    return score_candidate(text, CASES_BY_ID["test_add_execute"])
