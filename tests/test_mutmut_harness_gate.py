"""The harness mutation gate fails closed. It does not run mutmut."""

from __future__ import annotations

import importlib.util
import json
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def _checker():
    path = ROOT / "scripts" / "check-mutmut-harness.py"
    spec = importlib.util.spec_from_file_location("check_mutmut_harness", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECKER = _checker()


def _stats(**overrides: int) -> dict[str, object]:
    base: dict[str, object] = {
        "killed": 4,
        "survived": 0,
        "total": 4,
        "no_tests": 0,
        "skipped": 0,
        "suspicious": 0,
        "timeout": 0,
        "check_was_interrupted_by_user": 0,
        "segfault": 0,
    }
    base.update(overrides)
    return base


def _workflow_steps(text: str) -> list[dict[str, str]]:
    steps: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("- name:"):
            if current is not None:
                steps.append(current)
            current = {"name": stripped.split(":", 1)[1].strip()}
        elif current is not None and ":" in stripped:
            key, value = stripped.split(":", 1)
            current[key.strip()] = value.strip()
    if current is not None:
        steps.append(current)
    return steps


class MutationGateTests(unittest.TestCase):
    def test_killed_mutants_pass(self) -> None:
        self.assertIsNone(CHECKER.evaluate(_stats()))

    def test_survived_mutant_fails(self) -> None:
        self.assertEqual(CHECKER.evaluate(_stats(survived=1)), "survived 1")

    def test_empty_run_fails(self) -> None:
        self.assertEqual(CHECKER.evaluate(_stats(total=0, killed=0)), "no mutants")

    def test_zero_kills_fail(self) -> None:
        self.assertEqual(CHECKER.evaluate(_stats(killed=0, total=3)), "killed none")

    def test_timeout_fails(self) -> None:
        self.assertEqual(CHECKER.evaluate(_stats(timeout=1, total=5, killed=4)), "timeout 1")

    def test_no_tests_fail(self) -> None:
        self.assertEqual(CHECKER.evaluate(_stats(no_tests=2, total=6, killed=4)), "no_tests 2")

    def test_interrupted_run_fails(self) -> None:
        self.assertEqual(
            CHECKER.evaluate(_stats(check_was_interrupted_by_user=1)),
            "interrupted",
        )

    def test_main_rejects_a_stats_file_with_survivors(self) -> None:
        path = ROOT / "eval-runs" / "mutmut-stats-probe.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(_stats(survived=2, total=6, killed=4)),
            encoding="utf-8",
        )
        self.addCleanup(path.unlink)
        with patch("sys.argv", ["check-mutmut-harness.py", "--stats", str(path)]):
            self.assertEqual(CHECKER.main(), 1)


class MutationConfigTests(unittest.TestCase):
    def test_mutmut_targets_harness_module_only(self) -> None:
        data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        mutmut = data["tool"]["mutmut"]
        self.assertEqual(
            mutmut["only_mutate"],
            ["src/local_coding_slm/eval/harness.py"],
        )
        self.assertEqual(
            mutmut["pytest_add_cli_args_test_selection"],
            ["tests/test_harness_mutation.py"],
        )
        self.assertFalse(mutmut["use_git_change_detection"])
        self.assertTrue(mutmut["mutate_only_covered_lines"])

    def test_ci_runs_mutmut_on_harness_without_continue(self) -> None:
        text = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
        by_name = {step["name"]: step for step in _workflow_steps(text)}
        step = by_name["Mutation harness.py"]
        self.assertEqual(step["run"], "bash scripts/check-mutmut-harness.sh")
        self.assertNotIn("continue-on-error", step)
        script = (ROOT / "scripts" / "check-mutmut-harness.sh").read_text(encoding="utf-8")
        self.assertIn("mutmut run", script)
        self.assertIn("harness.py was not mutated", script)
        self.assertIn("check-mutmut-harness.py", script)
