"""MCP + apply-gate closed loop. Stub Ollama, no GPU."""

from __future__ import annotations

import unittest

from local_coding_slm.eval.harness import run_campaign, run_orchestrated_campaign
from local_coding_slm.eval.jobs import MCP_JOBS
from local_coding_slm.eval.record import summarize


class McpOrchestratorTests(unittest.IsolatedAsyncioTestCase):
    async def test_golden_corpus_pass_at_one(self) -> None:
        rows = await run_campaign(
            backend="stub",
            profile="golden",
            fast_ms=1,
            strong_ms=1,
        )
        stats = summarize(rows)
        self.assertGreaterEqual(stats["cases"], 10)
        self.assertEqual(stats["pass_at_1"], 1.0)
        self.assertEqual(stats["pass_end"], 1.0)

    async def test_keep_jobs_never_call_local(self) -> None:
        results = await run_orchestrated_campaign(
            backend="stub",
            profile="golden",
            job_ids=["keep_incident", "keep_architecture", "keep_ambiguous"],
            fast_ms=1,
            strong_ms=1,
        )
        self.assertEqual(len(results), 3)
        for item in results:
            self.assertFalse(item.delegated)
            self.assertEqual(item.outcome, "kept_on_premium")
            self.assertEqual(item.local_attempts, 0)
            self.assertIsNone(item.review_decision)

    async def test_mcp_accept_rewrite_reject(self) -> None:
        results = await run_orchestrated_campaign(
            backend="stub",
            profile="golden",
            job_ids=[
                "mcp_extract_accept",
                "mcp_move_accept",
                "mcp_code_rewrite",
                "mcp_reject_security",
                "mcp_review_notes_only",
            ],
            fast_ms=1,
            strong_ms=1,
        )
        by_id = {item.job: item for item in results}
        extract = by_id["mcp_extract_accept"]
        self.assertTrue(extract.delegated)
        self.assertEqual(extract.outcome, "applied_local")
        self.assertEqual(extract.apply_source, "local")
        self.assertTrue(extract.local_passed)
        self.assertGreater(extract.local_attempts, 0)

        moved = by_id["mcp_move_accept"]
        self.assertEqual(moved.outcome, "applied_local")
        self.assertIn("_normalize_whitespace", extract.applied_text or "")

        rewritten = by_id["mcp_code_rewrite"]
        self.assertEqual(rewritten.outcome, "applied_rewrite")
        self.assertEqual(rewritten.apply_source, "premium")
        self.assertIn("lo, hi = hi, lo", rewritten.applied_text or "")

        rejected = by_id["mcp_reject_security"]
        self.assertTrue(rejected.local_passed)
        self.assertEqual(rejected.outcome, "rejected")
        self.assertFalse(rejected.applied)
        self.assertIsNone(rejected.applied_text)

        notes = by_id["mcp_review_notes_only"]
        self.assertEqual(notes.case_id, "review_login")
        self.assertEqual(notes.outcome, "rejected")
        self.assertFalse(notes.applied)

    async def test_observed_move_repairs_then_accepts(self) -> None:
        results = await run_orchestrated_campaign(
            backend="stub",
            profile="observed",
            job_ids=["mcp_move_accept"],
            fast_ms=1,
            strong_ms=1,
        )
        item = results[0]
        self.assertEqual(item.local_models, ("fast", "fast"))
        self.assertEqual(item.outcome, "applied_local")

    def test_job_table_covers_keep_and_delegate(self) -> None:
        self.assertTrue(any(job.eval_case is None for job in MCP_JOBS))
        self.assertTrue(any(job.eval_case is not None for job in MCP_JOBS))


if __name__ == "__main__":
    unittest.main()
