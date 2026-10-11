"""Fitness function: the harness must not treat a skipped live check as success."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SkippedLiveFitnessTests(unittest.TestCase):
    def test_skipped_live_check_is_not_success(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
        env["OLLAMA_BASE_URL"] = "http://127.0.0.1:1"
        status_path = ROOT / "eval-runs" / "live-status.json"
        if status_path.exists():
            status_path.unlink()
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "run_eval.py"),
                "--live",
                "--case",
                "whitespace_extract",
            ],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("SKIP live", proc.stdout)
        payload = json.loads(status_path.read_text(encoding="utf-8"))
        self.assertEqual(payload, {"skipped": True})


if __name__ == "__main__":
    unittest.main()
