"""The personal host plan stays public-safe and ordered."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class HarnessHostPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = (ROOT / "docs" / "harness-host-plan.md").read_text(encoding="utf-8")
        self.example = (ROOT / ".env.example").read_text(encoding="utf-8")

    def test_halo_plan_precedes_downstairs_fallback(self) -> None:
        self.assertLess(
            self.plan.index("## Plan 1 — Halo / Ryzen AI Max+ 395"),
            self.plan.index("## Plan 2 — Downstairs / 4080-class fallback"),
        )
        self.assertIn("whitespace_extract", self.plan)
        self.assertIn("run_harness.py --backend live", self.plan)
        self.assertIn("run_eval.py --live --model fast", self.plan)
        self.assertIn("accept, rewrite, or reject", self.plan)

    def test_ports_are_loopback_and_distinct(self) -> None:
        for port in ("11434", "11436", "11438", "11440"):
            self.assertIn(port, self.plan)
            self.assertIn(port, self.example)
        # Paper host port is listed first in the ports table.
        self.assertLess(self.plan.index("11440"), self.plan.index("11436"))
        self.assertLess(self.plan.index("11436"), self.plan.index("11438"))
        self.assertLess(self.plan.index("11434"), self.plan.index("11438"))
        self.assertNotIn("192.168.", self.plan)
        self.assertNotIn("192.168.", self.example)

    def test_phase3_rows_target_halo(self) -> None:
        self.assertIn("Phase 3 paper timings run on the **Halo / GEEKOM 395**", self.plan)
        self.assertIn("host_class=downstairs-4080", self.plan)
        self.assertIn("halo-395", self.plan)
        roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")
        self.assertIn("harness-host-plan.md", roadmap)
        protocol = (ROOT / "docs" / "evaluation-protocol.md").read_text(encoding="utf-8")
        self.assertIn("harness-host-plan.md", protocol)
