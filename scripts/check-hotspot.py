#!/usr/bin/env python3
"""Hotspot gate: fail only when a changed Python file is both complex and hot.

Complex means some function's CCN is over the same cap as check-complexity.py.
Hot means the file is in the top git change-frequency set (top 10% of Python
files by commit touches, ties included). When that cutoff is no higher than
the least-touched file, there is no frequency signal and the gate passes.
A change in a quiet file passes even if the file is complex.
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from math import ceil
from pathlib import Path

TOP_FRACTION = 0.10
DEFAULT_CCN = 10


def load_complexity():
    path = Path(__file__).resolve().with_name("check-complexity.py")
    spec = importlib.util.spec_from_file_location("slm_check_complexity", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def touch_counts(repo: Path) -> dict[str, int]:
    log = subprocess.check_output(
        ["git", "log", "--pretty=format:", "--name-only"],
        cwd=repo,
        text=True,
    )
    counts: dict[str, int] = {}
    for line in log.splitlines():
        rel = line.strip()
        if Path(rel).suffix != ".py":
            continue
        counts[rel] = counts.get(rel, 0) + 1
    return counts


def top_frequency(counts: dict[str, int]) -> set[str]:
    if not counts:
        return set()
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    k = max(1, ceil(len(ranked) * TOP_FRACTION))
    cutoff = ranked[k - 1][1]
    least = min(count for _, count in ranked)
    if cutoff <= least:
        return set()
    return {path for path, count in ranked if count >= cutoff}


def max_ccn(rows: list[dict[str, str]]) -> int:
    best = 0
    for row in rows:
        value = int(row["ccn"])
        if value > best:
            best = value
    return best


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--ccn", type=int, default=DEFAULT_CCN)
    parser.add_argument("--paths", nargs="*", default=["."])
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    complexity = load_complexity()
    try:
        files = complexity.changed_files(repo, args.base, args.paths, {".py"})
        counts = touch_counts(repo)
    except subprocess.CalledProcessError as exc:
        print(f"git failed: {exc}", file=sys.stderr)
        return 2
    if not files:
        print("check-hotspot: no changed python files")
        return 0
    hot = top_frequency(counts)
    failures: list[str] = []
    for rel in files:
        if rel not in hot:
            continue
        src = complexity.file_at(repo, "HEAD", rel)
        if src is None:
            continue
        ccn = max_ccn(complexity.lizard_rows(src, rel, "python"))
        if ccn > args.ccn:
            failures.append(f"HOTSPOT {rel} CCN={ccn} touches={counts.get(rel, 0)}")
    if failures:
        print("check-hotspot: FAIL", file=sys.stderr)
        for line in failures:
            print(line, file=sys.stderr)
        return 1
    print(f"check-hotspot: PASS ({len(files)} file(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
