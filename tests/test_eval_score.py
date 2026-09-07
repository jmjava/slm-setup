"""Fixture scoring for the evaluation protocol. No Ollama."""

from __future__ import annotations

import unittest

from local_coding_slm.eval.cases import CASES_BY_ID, FIXTURES, SEED_CASE_IDS
from local_coding_slm.eval.score import score_candidate


class FixtureCorpusTests(unittest.TestCase):
    def test_every_fixture_matches_expected_layer(self) -> None:
        self.assertGreaterEqual(len(FIXTURES), 16)
        self.assertGreaterEqual(len(SEED_CASE_IDS), 4)
        for fixture in FIXTURES:
            with self.subTest(fixture=fixture.name):
                case = CASES_BY_ID[fixture.case_id]
                result = score_candidate(fixture.text, case)
                self.assertEqual(result.passed, fixture.expect_pass, result.layers)
                failure = result.first_failure
                if fixture.expect_first is None:
                    self.assertIsNone(failure)
                    continue
                self.assertIsNotNone(failure)
                assert failure is not None
                self.assertEqual(failure.name, fixture.expect_first)

    def test_nested_helper_is_structure_not_behavior(self) -> None:
        case = CASES_BY_ID["whitespace_extract"]
        nested = next(item for item in FIXTURES if item.name == "whitespace_nested_helper")
        result = score_candidate(nested.text, case)
        self.assertEqual(result.layer("transport").status, "pass")
        self.assertEqual(result.layer("format").status, "pass")
        self.assertEqual(result.layer("structure").status, "fail")
        self.assertEqual(result.layer("behavior").status, "skip")
        self.assertIn("nested inside", result.layer("structure").message)

    def test_wrong_assert_is_behavior_not_shape(self) -> None:
        case = CASES_BY_ID["test_add_execute"]
        bad = next(item for item in FIXTURES if item.name == "test_add_wrong_assert")
        result = score_candidate(bad.text, case)
        self.assertEqual(result.layer("format").status, "pass")
        self.assertEqual(result.layer("structure").status, "pass")
        self.assertEqual(result.layer("behavior").status, "fail")

    def test_vague_and_precise_share_the_same_checker(self) -> None:
        precise = CASES_BY_ID["whitespace_extract"]
        vague = CASES_BY_ID["whitespace_extract_vague"]
        self.assertEqual(precise.required_top_level, vague.required_top_level)
        self.assertEqual(precise.behavior, vague.behavior)
        self.assertNotEqual(precise.task, vague.task)

    def test_corpus_covers_all_generation_tools(self) -> None:
        from local_coding_slm.eval.cases import CASES

        tools = {case.tool for case in CASES}
        self.assertTrue(
            {
                "local_code",
                "local_explain",
                "local_generate_tests",
                "local_refactor",
                "local_review",
            }.issubset(tools)
        )

    def test_prose_explain_missing_phrase_is_structure(self) -> None:
        case = CASES_BY_ID["explain_clamp"]
        vague = next(item for item in FIXTURES if item.name == "explain_clamp_vague")
        result = score_candidate(vague.text, case)
        self.assertEqual(result.layer("format").status, "pass")
        self.assertEqual(result.layer("structure").status, "fail")
        self.assertEqual(result.layer("behavior").status, "skip")
        self.assertIn("hi", result.layer("structure").message)

    def test_move_partial_is_format_not_behavior(self) -> None:
        case = CASES_BY_ID["move_function_imports"]
        partial = next(item for item in FIXTURES if item.name == "move_function_partial")
        result = score_candidate(partial.text, case)
        self.assertEqual(result.layer("format").status, "fail")
        self.assertEqual(result.layer("behavior").status, "skip")


if __name__ == "__main__":
    unittest.main()
