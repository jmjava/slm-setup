"""Smell gates bound to the unit job: unused imports and new CCN fail."""

from __future__ import annotations

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class QualityGateTests(unittest.TestCase):
    def test_ruff_unused_imports(self) -> None:
        ruff = shutil.which("ruff")
        cmd = (
            [ruff, "check", "--select", "F401,F811", "src", "scripts", "tests"]
            if ruff
            else [sys.executable, "-m", "ruff", "check", "--select", "F401,F811", "src", "scripts", "tests"]
        )
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_complexity_gate_proves_new_ccn_fails(self) -> None:
        script = ROOT / "scripts" / "test-check-complexity.sh"
        proc = subprocess.run(["bash", str(script)], cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("test-check-complexity: PASS", proc.stdout)


if __name__ == "__main__":
    unittest.main()
