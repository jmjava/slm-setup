#!/usr/bin/env python3
"""Frozen pyflakes baseline.

Current findings must be covered by config/ruff/baseline.txt (one
path<TAB>code per allowed occurrence). A higher count fails. A finding
that is gone may leave a stale line; this script never rewrites the file.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "ruff" / "ruff.toml"
DEFAULT_BASELINE = ROOT / "config" / "ruff" / "baseline.txt"
DEFAULT_PATHS = ["src", "scripts", "tests"]


def refuse_rewrite(argv: list[str]) -> None:
    blocked = {"--write-baseline", "--create-baseline", "-cb"}
    if blocked.intersection(argv):
        print("refusing to rewrite the ruff baseline", file=sys.stderr)
        raise SystemExit(1)


def ruff_argv() -> list[str]:
    if shutil.which("ruff"):
        return ["ruff"]
    return [sys.executable, "-m", "ruff"]


def rel_path(filename: str, root: Path) -> str:
    path = Path(filename)
    if path.is_absolute():
        try:
            path = path.relative_to(root)
        except ValueError:
            return filename.replace("\\", "/")
    return path.as_posix()


def run_ruff(root: Path, config: Path, paths: list[str]) -> list[dict]:
    if shutil.which("ruff") is None:
        try:
            probe = subprocess.run(
                [sys.executable, "-m", "ruff", "version"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            print(f"ruff is not installed: {exc}", file=sys.stderr)
            raise SystemExit(2) from exc
        if probe.returncode != 0:
            print("ruff is not installed; no baseline comparison was invented", file=sys.stderr)
            raise SystemExit(2)
    cmd = [
        *ruff_argv(),
        "check",
        "--config",
        str(config),
        "--output-format",
        "json",
        "--exit-zero",
        *paths,
    ]
    result = subprocess.run(cmd, cwd=root, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        sys.stderr.write(result.stderr or result.stdout)
        raise SystemExit(result.returncode or 2)
    text = result.stdout.strip() or "[]"
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise SystemExit(2) from None
    if not isinstance(payload, list):
        print("ruff did not return a finding list", file=sys.stderr)
        raise SystemExit(2)
    return payload


def current_counts(payload: list[dict], root: Path) -> Counter[tuple[str, str]]:
    counts: Counter[tuple[str, str]] = Counter()
    for item in payload:
        code = str(item.get("code") or "")
        filename = rel_path(str(item.get("filename") or ""), root)
        if code and filename:
            counts[(filename, code)] += 1
    return counts


def load_baseline(path: Path) -> Counter[tuple[str, str]]:
    if not path.is_file():
        print(f"missing ruff baseline: {path}", file=sys.stderr)
        raise SystemExit(2)
    counts: Counter[tuple[str, str]] = Counter()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        filename, code = line.split("\t", 1)
        counts[(filename, code)] += 1
    return counts


def new_findings(
    current: Counter[tuple[str, str]], baseline: Counter[tuple[str, str]]
) -> list[str]:
    failures = []
    for key, count in sorted(current.items()):
        allowed = baseline.get(key, 0)
        if count > allowed:
            failures.append(f"NEW {key[0]} {key[1]} count {allowed} -> {count}")
    return failures


def main() -> int:
    refuse_rewrite(sys.argv[1:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args()
    root = args.root.resolve()
    config = args.config if args.config.is_absolute() else (root / args.config).resolve()
    baseline_path = args.baseline if args.baseline.is_absolute() else (root / args.baseline).resolve()
    paths = args.paths or DEFAULT_PATHS
    if not config.is_file():
        print(f"missing ruff config: {config}", file=sys.stderr)
        return 2
    baseline = load_baseline(baseline_path)
    before = baseline_path.read_bytes()
    current = current_counts(run_ruff(root, config, paths), root)
    if baseline_path.read_bytes() != before:
        print("ruff baseline was rewritten", file=sys.stderr)
        return 1
    failures = new_findings(current, baseline)
    if failures:
        print("check-static-baseline: FAIL", file=sys.stderr)
        for line in failures:
            print(line, file=sys.stderr)
        return 1
    print(f"check-static-baseline: PASS ({sum(current.values())} finding(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
