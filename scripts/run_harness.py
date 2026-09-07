#!/usr/bin/env python3
"""Measure delegated local_* work. Stub Ollama in cloud; --backend live on GPU."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from local_coding_slm.eval.harness import format_summary, run_campaign  # noqa: E402
from local_coding_slm.eval.record import summarize, write_jsonl  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("stub", "live"), default="stub")
    parser.add_argument("--profile", choices=("golden", "observed"), default="golden")
    parser.add_argument("--case", action="append", dest="case_ids", default=None)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--fast-ms", type=float, default=8.0)
    parser.add_argument("--strong-ms", type=float, default=25.0)
    parser.add_argument(
        "--out",
        default="",
        help="Directory for attempts.jsonl and summary.json (gitignored eval-runs/)",
    )
    args = parser.parse_args()
    rows = asyncio.run(
        run_campaign(
            backend=args.backend,
            profile=args.profile,
            case_ids=args.case_ids,
            repeat=args.repeat,
            fast_ms=args.fast_ms,
            strong_ms=args.strong_ms,
        )
    )
    print(format_summary(rows))
    if args.out:
        dest = Path(args.out)
        dest.mkdir(parents=True, exist_ok=True)
        write_jsonl(str(dest / "attempts.jsonl"), rows)
        (dest / "summary.json").write_text(
            json.dumps(summarize(rows), indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {dest / 'attempts.jsonl'}")
    raise SystemExit(0 if rows else 1)


if __name__ == "__main__":
    main()
