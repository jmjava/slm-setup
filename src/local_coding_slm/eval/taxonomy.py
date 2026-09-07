"""Case categories for stratified harness stats. Not a task classifier."""

from __future__ import annotations

CATEGORIES: dict[str, str] = {
    "whitespace_extract": "extract",
    "whitespace_extract_vague": "prompt_contract",
    "multi_file_rename": "rename",
    "test_add_execute": "tests",
    "move_function_imports": "extract",
    "extract_shared_parser": "extract",
    "split_pipeline": "split",
    "implement_clamp": "implement",
    "explain_clamp": "explain",
    "review_login": "review",
    "extract_dataclass": "extract",
    "extract_dataclass_vague": "prompt_contract",
    "rename_three_files": "rename",
    "split_settings": "split",
    "implement_slug": "implement",
    "implement_median": "implement",
    "test_clamp_execute": "tests",
    "test_median_execute": "tests",
    "explain_mean": "explain",
    "review_divzero": "review",
}


def category_of(case_id: str) -> str:
    from local_coding_slm.eval.cases import CASES_BY_ID

    case = CASES_BY_ID.get(case_id)
    if case is not None:
        return case.category
    return CATEGORIES.get(case_id, "other")
