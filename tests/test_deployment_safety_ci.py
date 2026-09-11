"""CI must run the deployment safety checker and be able to fail. No GPU."""

from __future__ import annotations

import importlib.util
import io
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from local_coding_slm.safety import CheckResult

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"
SCRIPT = ROOT / "scripts" / "check_deployment_safety.py"
DEPLOYMENT_SAFETY = "Deployment safety"
CI_COMMAND = "python scripts/check_deployment_safety.py --skip-listen"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_deployment_safety", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_main(module: ModuleType, argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with patch.object(sys, "argv", argv), redirect_stdout(stdout), redirect_stderr(stderr):
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


class DeploymentSafetyCiTests(unittest.TestCase):
    def test_ci_deployment_safety_can_go_red(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        by_name = {step["name"]: step for step in _workflow_steps(text)}
        self.assertIn(DEPLOYMENT_SAFETY, by_name)
        step = by_name[DEPLOYMENT_SAFETY]
        self.assertEqual(step.get("run", ""), CI_COMMAND)
        self.assertNotIn("continue-on-error", step)

    def test_skip_listen_exits_0_on_current_repo(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--skip-listen"],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("deployment safety", proc.stdout)

    def test_hostname_url_fails_deployment_safety(self) -> None:
        module = _load_script()
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "https://my-ollama.evil.com"}):
            code, stdout, stderr = _run_main(
                module, [str(SCRIPT), "--skip-listen"]
            )
        self.assertEqual(code, 1, stderr)
        self.assertIn("FAIL deployment safety", stdout)
        self.assertNotIn("PASS deployment safety (warnings)", stdout)

    def test_skip_listen_exits_1_when_checks_fail(self) -> None:
        module = _load_script()
        failed = [
            CheckResult("base_url", "fail", "OLLAMA_BASE_URL must not use a wildcard bind address"),
        ]
        with patch.object(module, "run_checks", return_value=failed):
            code, stdout, stderr = _run_main(
                module, [str(SCRIPT), "--skip-listen"]
            )
        self.assertEqual(code, 1, stderr)
        self.assertIn("FAIL deployment safety", stdout)


if __name__ == "__main__":
    unittest.main()
