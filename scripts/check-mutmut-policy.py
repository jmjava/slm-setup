#!/usr/bin/env python3
"""Run mutmut on the harness retry policy and fail if the kill ratio drops.

Reads scripts/mutmut-policy-floor.json. Does not rewrite that floor.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOOR = ROOT / "scripts" / "mutmut-policy-floor.json"
STATS = ROOT / "mutants" / "mutmut-cicd-stats.json"


def decisive(stats: dict[str, int]) -> tuple[int, int]:
    killed = int(stats["killed"])
    survived = int(stats["survived"]) + int(stats["suspicious"]) + int(stats["timeout"])
    return killed, killed + survived


def main() -> int:
    if shutil.which("mutmut") is None:
        print("mutmut is not installed; no mutation score was invented", file=sys.stderr)
        return 2
    if not FLOOR.is_file():
        print(f"missing floor {FLOOR}", file=sys.stderr)
        return 2
    floor = json.loads(FLOOR.read_text(encoding="utf-8"))
    run = subprocess.run(["mutmut", "run"], cwd=ROOT, check=False)
    if run.returncode != 0:
        print(f"mutmut run exited {run.returncode}", file=sys.stderr)
        return run.returncode
    exported = subprocess.run(["mutmut", "export-cicd-stats"], cwd=ROOT, check=False)
    if exported.returncode != 0 or not STATS.is_file():
        print("mutmut export-cicd-stats did not write a score", file=sys.stderr)
        return exported.returncode or 2
    stats = json.loads(STATS.read_text(encoding="utf-8"))
    killed, checked = decisive(stats)
    floor_killed = int(floor["killed"])
    floor_checked = int(floor["checked"])
    print(
        f"mutmut policy.py: killed={killed} checked={checked} "
        f"floor={floor_killed}/{floor_checked}"
    )
    if checked <= 0 or killed <= 0:
        print("no killed mutants; refusing to treat that as a score", file=sys.stderr)
        return 1
    if killed * floor_checked < floor_killed * checked:
        print("mutation kill ratio dropped below the recorded floor", file=sys.stderr)
        return 1
    print("check-mutmut-policy: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
