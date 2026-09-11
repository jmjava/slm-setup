"""Offline scoring for the harder multi-file refactor corpus. No Ollama."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from local_coding_slm.eval.cases import CASES_BY_ID, FIXTURES
from local_coding_slm.eval.cases_harder import HARDER_CASE_IDS
from local_coding_slm.eval.score import score_candidate

ROOT = Path(__file__).resolve().parents[1]


def _fixture(name: str):
    return next(item for item in FIXTURES if item.name == name)


class HarderMultifileCorpusTests(unittest.TestCase):
    def test_harder_cases_span_more_than_one_file(self) -> None:
        self.assertEqual(len(HARDER_CASE_IDS), 6)
        for case_id in HARDER_CASE_IDS:
            with self.subTest(case_id=case_id):
                case = CASES_BY_ID[case_id]
                self.assertEqual(case.tool, "local_refactor")
                self.assertGreaterEqual(len(case.required_paths), 2)
                self.assertTrue(case.behavior or case.behavior_fn is not None)

    def test_goldens_pass_all_four_layers(self) -> None:
        for name in (
            "rename_exception_golden",
            "rename_field_golden",
            "widen_return_golden",
            "rename_kwarg_golden",
            "rename_payload_golden",
            "rename_env_golden",
        ):
            with self.subTest(fixture=name):
                fixture = _fixture(name)
                result = score_candidate(fixture.text, CASES_BY_ID[fixture.case_id])
                self.assertTrue(result.passed, result.layers)
                for layer in ("transport", "format", "structure", "behavior"):
                    self.assertEqual(result.layer(layer).status, "pass")

    def test_alias_and_int_return_are_structure_not_behavior(self) -> None:
        for name in (
            "rename_exception_alias",
            "rename_field_alias",
            "widen_return_int",
            "rename_kwarg_alias",
            "rename_payload_alias",
            "rename_env_alias",
        ):
            with self.subTest(fixture=name):
                fixture = _fixture(name)
                result = score_candidate(fixture.text, CASES_BY_ID[fixture.case_id])
                self.assertEqual(result.layer("format").status, "pass")
                self.assertEqual(result.layer("structure").status, "fail")
                self.assertEqual(result.layer("behavior").status, "skip")

    def test_threshold_format_and_rate_are_behavior(self) -> None:
        for name in (
            "rename_exception_threshold",
            "rename_field_format",
            "widen_return_wrong_rate",
            "rename_kwarg_separator",
            "rename_payload_prefix",
            "rename_env_prefix",
        ):
            with self.subTest(fixture=name):
                fixture = _fixture(name)
                result = score_candidate(fixture.text, CASES_BY_ID[fixture.case_id])
                self.assertEqual(result.layer("structure").status, "pass")
                self.assertEqual(result.layer("behavior").status, "fail")

    def test_live_flag_skips_when_ollama_is_down(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
        env["OLLAMA_BASE_URL"] = "http://127.0.0.1:1"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "prove_multifile_refactor.py"),
                "--live",
            ],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("SKIP live", proc.stdout)

    def test_require_live_exits_2_when_ollama_is_down(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
        env["OLLAMA_BASE_URL"] = "http://127.0.0.1:1"
        status_path = ROOT / "eval-runs" / "live-status.json"
        if status_path.exists():
            status_path.unlink()
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "prove_multifile_refactor.py"),
                "--live",
                "--require-live",
            ],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("SKIP live", proc.stdout)
        payload = json.loads(status_path.read_text(encoding="utf-8"))
        self.assertEqual(payload, {"skipped": True})

    def test_partial_files_are_format(self) -> None:
        for name in (
            "rename_exception_partial",
            "rename_field_partial",
            "widen_return_partial",
            "rename_kwarg_partial",
            "rename_payload_partial",
            "rename_env_partial",
        ):
            with self.subTest(fixture=name):
                fixture = _fixture(name)
                result = score_candidate(fixture.text, CASES_BY_ID[fixture.case_id])
                self.assertEqual(result.layer("format").status, "fail")
                self.assertEqual(result.layer("behavior").status, "skip")


if __name__ == "__main__":
    unittest.main()
