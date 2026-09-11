#!/usr/bin/env python3
"""Score the harder multi-file refactor corpus.

Default path is offline fixtures (CI / no GPU). ``--live`` calls real
``local_refactor`` through stdio MCP and skips with exit 0 when Ollama
is down. ``--require-live`` is the same path but exits 2 on skip and
writes ``eval-runs/live-status.json``. A skip is not a model-quality pass.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--require-live", action="store_true")
    parser.add_argument("--model", choices=("fast", "strong"), default="fast")
    parser.add_argument("--case", dest="case_id", default=None)
    args = parser.parse_args()
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "run_eval.py"),
        "--suite",
        "harder",
    ]
    if args.live or args.require_live:
        cmd.extend(["--live", "--model", args.model])
    if args.require_live:
        cmd.append("--require-live")
    if args.case_id:
        cmd.extend(["--case", args.case_id])
    raise SystemExit(subprocess.call(cmd, cwd=str(ROOT)))


if __name__ == "__main__":
    main()
