"""Scripted orchestrator exits on apply-triple mismatch. No GPU."""

from __future__ import annotations

import importlib.util
import io
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"
SCRIPT = ROOT / "scripts" / "run_orchestration.py"
SCRIPTED_ORCHESTRATOR = "Scripted orchestrator"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("run_orchestration", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_main(module: ModuleType) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            module.main()
        except SystemExit as exc:
            code = 0 if exc.code is None else int(exc.code)
            return code, stdout.getvalue(), stderr.getvalue()
    raise AssertionError("main() returned without SystemExit")


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


class OrchestrationExitTests(unittest.TestCase):
    def test_main_exits_0_when_contract_holds(self) -> None:
        module = _load_script()
        code, stdout, stderr = _run_main(module)
        self.assertEqual(code, 0, stderr)
        self.assertIn('"jobs": 8', stdout)
        self.assertEqual(stderr, "")

    def test_sabotaged_expected_exits_1(self) -> None:
        module = _load_script()
        sabotaged = dict(module.EXPECTED)
        sabotaged["keep_incident"] = ("applied_local", True, "local")
        with patch.object(module, "EXPECTED", sabotaged):
            code, _stdout, stderr = _run_main(module)
        self.assertEqual(code, 1)
        self.assertIn("keep_incident", stderr)
        self.assertIn("applied_local", stderr)
        self.assertIn("kept_on_premium", stderr)

    def test_mocked_wrong_outcome_exits_1(self) -> None:
        module = _load_script()
        real_run_job = module.run_job

        def lie(job: object) -> object:
            result = real_run_job(job)
            if result.job == "delegate_accept":
                return replace(result, outcome="rejected", applied=False, apply_source=None)
            return result

        with patch.object(module, "run_job", lie):
            code, _stdout, stderr = _run_main(module)
        self.assertEqual(code, 1)
        self.assertIn("delegate_accept", stderr)
        self.assertIn("rejected", stderr)
        self.assertIn("applied_local", stderr)

    def test_script_process_exits_0(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('"jobs": 8', proc.stdout)

    def test_ci_scripted_orchestrator_can_go_red(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        by_name = {step["name"]: step for step in _workflow_steps(text)}
        self.assertIn(SCRIPTED_ORCHESTRATOR, by_name)
        step = by_name[SCRIPTED_ORCHESTRATOR]
        self.assertIn("scripts/run_orchestration.py", step.get("run", ""))
        self.assertNotIn("continue-on-error", step)


if __name__ == "__main__":
    unittest.main()
