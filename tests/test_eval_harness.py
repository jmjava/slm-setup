"""Policy, stub Ollama, and closed-loop harness measurements. No GPU."""

from __future__ import annotations

import os
import unittest
from urllib.request import urlopen

from local_coding_slm.eval.cases import CASES_BY_ID, SEED_CASE_IDS, WHITESPACE_TASK
from local_coding_slm.eval.harness import run_campaign
from local_coding_slm.eval.policy import next_plan
from local_coding_slm.eval.record import AttemptRecord, summarize
from local_coding_slm.eval.stub_ollama import StubOllama
from local_coding_slm.ollama_client import chat, list_model_names, status_report


def _rec(**kwargs: object) -> AttemptRecord:
    base: dict[str, object] = {
        "job": "whitespace_extract#1",
        "case_id": "whitespace_extract",
        "attempt": 1,
        "model": "fast",
        "suffix": "",
        "passed": False,
        "first_failure": "format",
        "mcp_ms": 1.0,
        "score_ms": 0.2,
        "elapsed_ms": 1.2,
        "response_chars": 10,
        "backend": "stub",
        "profile": "observed",
        "layers": {"transport": "pass", "format": "fail"},
    }
    base.update(kwargs)
    return AttemptRecord(**base)  # type: ignore[arg-type]


class PolicyTests(unittest.TestCase):
    def test_starts_fast(self) -> None:
        plan = next_plan(CASES_BY_ID["whitespace_extract"], [])
        assert plan is not None
        self.assertEqual(plan.model, "fast")
        self.assertEqual(plan.suffix, "")

    def test_format_repair_stays_fast(self) -> None:
        plan = next_plan(
            CASES_BY_ID["whitespace_extract"],
            [_rec(first_failure="format")],
        )
        assert plan is not None
        self.assertEqual(plan.model, "fast")
        self.assertIn("fenced", plan.suffix)

    def test_behavior_escalates(self) -> None:
        plan = next_plan(
            CASES_BY_ID["test_add_execute"],
            [_rec(case_id="test_add_execute", first_failure="behavior")],
        )
        assert plan is not None
        self.assertEqual(plan.model, "strong")

    def test_accepted_stops(self) -> None:
        self.assertIsNone(
            next_plan(
                CASES_BY_ID["whitespace_extract"],
                [_rec(passed=True, first_failure=None)],
            )
        )


class StubHttpTests(unittest.TestCase):
    def test_loopback_tags_and_chat(self) -> None:
        with StubOllama(profile="golden", fast_ms=1, strong_ms=1) as stub:
            self.assertTrue(stub.base_url.startswith("http://127.0.0.1:"))
            os.environ["OLLAMA_BASE_URL"] = stub.base_url
            self.addCleanup(lambda: os.environ.pop("OLLAMA_BASE_URL", None))
            names = list_model_names()
            self.assertTrue(any("qwen3.5:9b" in n for n in names))
            report = status_report()
            self.assertIn("ok=true", report)
            text = chat("sys", WHITESPACE_TASK, model="fast")
            self.assertIn("_normalize_whitespace", text)
            with urlopen(stub.base_url + "/api/tags", timeout=2) as resp:
                self.assertEqual(resp.status, 200)


class HarnessTests(unittest.IsolatedAsyncioTestCase):
    async def test_golden_pass_at_one(self) -> None:
        rows = await run_campaign(
            backend="stub",
            profile="golden",
            case_ids=["whitespace_extract"],
            fast_ms=1,
            strong_ms=1,
        )
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].passed)
        self.assertEqual(rows[0].attempt, 1)
        self.assertEqual(rows[0].job, "whitespace_extract#1")
        self.assertGreater(rows[0].elapsed_ms, 0)
        self.assertEqual(rows[0].layers["behavior"], "pass")

    async def test_repeat_is_separate_jobs(self) -> None:
        rows = await run_campaign(
            backend="stub",
            profile="golden",
            case_ids=["test_add_execute"],
            repeat=2,
            fast_ms=1,
            strong_ms=1,
        )
        stats = summarize(rows)
        self.assertEqual(stats["cases"], 2)
        self.assertEqual(stats["pass_at_1"], 1.0)
        self.assertEqual({row.job for row in rows}, {"test_add_execute#1", "test_add_execute#2"})

    async def test_observed_campaign_records_layers(self) -> None:
        rows = await run_campaign(
            backend="stub",
            profile="observed",
            case_ids=list(SEED_CASE_IDS),
            fast_ms=1,
            strong_ms=1,
        )
        stats = summarize(rows)
        self.assertEqual(stats["cases"], 4)
        self.assertEqual(stats["pass_at_1"], 0.0)
        self.assertEqual(stats["pass_end"], 1.0)
        self.assertGreater(stats["attempts"], 4)
        self.assertIn("format", stats["first_failure"])
        self.assertIn("structure", stats["first_failure"])
        self.assertIn("behavior", stats["first_failure"])
        vague = [row for row in rows if row.case_id == "whitespace_extract_vague"]
        self.assertTrue(any(row.model == "strong" and row.passed for row in vague))


if __name__ == "__main__":
    unittest.main()
