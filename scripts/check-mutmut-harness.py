#!/usr/bin/env python3
"""Fail unless mutmut killed every harness.py mutant.

Reads mutants/mutmut-cicd-stats.json. There is no survived ceiling.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATS = ROOT / "mutants" / "mutmut-cicd-stats.json"
_BAD_KEYS = ("survived", "no_tests", "timeout", "suspicious", "segfault", "skipped")


def _as_int(stats: dict[str, object], key: str) -> int:
    value = stats.get(key) or 0
    return int(value)  # type: ignore[arg-type]


def evaluate(stats: dict[str, object]) -> str | None:
    if _as_int(stats, "check_was_interrupted_by_user") > 0:
        return "interrupted"
    if _as_int(stats, "total") <= 0:
        return "no mutants"
    if _as_int(stats, "killed") <= 0:
        return "killed none"
    for key in _BAD_KEYS:
        count = _as_int(stats, key)
        if count > 0:
            return f"{key} {count}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stats", type=Path, default=DEFAULT_STATS)
    args = parser.parse_args()
    if not args.stats.is_file():
        print(f"check-mutmut-harness: missing {args.stats}", file=sys.stderr)
        return 2
    stats = json.loads(args.stats.read_text(encoding="utf-8"))
    error = evaluate(stats)
    if error is not None:
        print(f"check-mutmut-harness: FAIL {error}", file=sys.stderr)
        return 1
    print(
        "check-mutmut-harness: PASS "
        f"killed {_as_int(stats, 'killed')} of {_as_int(stats, 'total')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
