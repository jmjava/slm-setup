"""Stratified pass@1 / pass@end by tool and category."""

from __future__ import annotations

import unittest

from local_coding_slm.eval.record import AttemptRecord
from local_coding_slm.eval.stats import enrich_summary


def _rec(**kwargs: object) -> AttemptRecord:
    base: dict[str, object] = {
        "job": "whitespace_extract#1",
        "case_id": "whitespace_extract",
        "attempt": 1,
        "model": "fast",
        "suffix": "",
        "passed": True,
        "first_failure": None,
        "mcp_ms": 1.0,
        "score_ms": 0.2,
        "elapsed_ms": 1.2,
        "response_chars": 10,
        "backend": "stub",
        "profile": "golden",
        "layers": {"transport": "pass", "format": "pass", "structure": "pass", "behavior": "pass"},
    }
    base.update(kwargs)
    return AttemptRecord(**base)  # type: ignore[arg-type]


class EnrichSummaryTests(unittest.TestCase):
    def test_by_tool_and_category(self) -> None:
        rows = [
            _rec(),
            _rec(
                job="implement_clamp#1",
                case_id="implement_clamp",
                passed=False,
                first_failure="behavior",
                layers={"transport": "pass", "format": "pass", "structure": "pass", "behavior": "fail"},
            ),
            _rec(
                job="implement_clamp#1",
                case_id="implement_clamp",
                attempt=2,
                model="strong",
                passed=True,
                first_failure=None,
            ),
            _rec(
                job="explain_clamp#1",
                case_id="explain_clamp",
                passed=True,
            ),
        ]
        stats = enrich_summary(rows)
        self.assertEqual(stats["cases"], 3)
        self.assertAlmostEqual(stats["pass_at_1"], 2 / 3)
        self.assertEqual(stats["pass_end"], 1.0)
        by_tool = stats["by_tool"]
        self.assertEqual(by_tool["local_refactor"]["cases"], 1)
        self.assertEqual(by_tool["local_refactor"]["pass_at_1"], 1.0)
        self.assertEqual(by_tool["local_code"]["cases"], 1)
        self.assertEqual(by_tool["local_code"]["pass_at_1"], 0.0)
        self.assertEqual(by_tool["local_code"]["pass_end"], 1.0)
        self.assertEqual(by_tool["local_code"]["escalated"], 1.0)
        by_category = stats["by_category"]
        self.assertEqual(by_category["extract"]["pass_at_1"], 1.0)
        self.assertEqual(by_category["implement"]["pass_at_1"], 0.0)
        self.assertEqual(by_category["explain"]["pass_at_1"], 1.0)
        self.assertIn("behavior", by_tool["local_code"]["first_failure"])


if __name__ == "__main__":
    unittest.main()
