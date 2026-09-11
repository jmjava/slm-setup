"""Harness exits on pass@end, not row count. Stub sabotage, no GPU."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

from local_coding_slm.eval.harness import harness_exit_code

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"
STUB_MCP_STEPS = (
    "Stub MCP golden",
    "Stub MCP + apply gate",
    "Stub MCP observed failover",
)


def _run_harness(*args: str, refuse: bool = False) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    if refuse:
        env["LOCAL_CODING_SLM_STUB_REFUSE"] = "1"
    else:
        env.pop("LOCAL_CODING_SLM_STUB_REFUSE", None)
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_harness.py"), *args],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _workflow_steps(text: str) -> list[dict[str, str]]:
    steps: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("- name:"):
            if current is not None:
                steps.append(current)
            current = {"name": stripped.split(":", 1)[1].strip()}
        elif current is not None and stripped.startswith("run:"):
            current["run"] = stripped.split(":", 1)[1].strip()
        elif current is not None and stripped.startswith("continue-on-error:"):
            current["continue-on-error"] = stripped.split(":", 1)[1].strip()
    if current is not None:
        steps.append(current)
    return steps


class HarnessExitCodeTests(unittest.TestCase):
    def test_empty_or_zero_pass_end_is_failure(self) -> None:
        self.assertEqual(harness_exit_code(0.0, 0), 1)
        self.assertEqual(harness_exit_code(0.0, 4), 1)

    def test_positive_pass_end_respects_minimum(self) -> None:
        self.assertEqual(harness_exit_code(1.0, 4), 0)
        self.assertEqual(harness_exit_code(0.5, 4, min_pass_end=1.0), 1)
        self.assertEqual(harness_exit_code(1.0, 4, min_pass_end=1.0), 0)


class HarnessRefuseExitTests(unittest.TestCase):
    def test_stub_refuse_every_call_exits_nonzero(self) -> None:
        proc = _run_harness(
            "--backend",
            "stub",
            "--profile",
            "golden",
            "--fast-ms",
            "1",
            "--strong-ms",
            "1",
            "--case",
            "whitespace_extract",
            refuse=True,
        )
        self.assertNotEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("pass@end=0.00", proc.stdout)
        self.assertIn("whitespace_extract#1", proc.stdout)

    def test_ci_stub_mcp_steps_invoke_harness_without_continue(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        by_name = {step["name"]: step for step in _workflow_steps(text)}
        for name in STUB_MCP_STEPS:
            with self.subTest(step=name):
                self.assertIn(name, by_name)
                run = by_name[name].get("run", "")
                self.assertIn("scripts/run_harness.py", run)
                self.assertNotIn("continue-on-error", by_name[name])


if __name__ == "__main__":
    unittest.main()
