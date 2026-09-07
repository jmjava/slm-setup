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

from local_coding_slm.eval.harness import (  # noqa: E402
    format_orchestrated,
    format_summary,
    run_campaign,
    run_orchestrated_campaign,
)
from local_coding_slm.eval.record import summarize, write_jsonl  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("stub", "live"), default="stub")
    parser.add_argument("--profile", choices=("golden", "observed"), default="golden")
    parser.add_argument("--case", action="append", dest="case_ids", default=None)
    parser.add_argument("--job", action="append", dest="job_ids", default=None)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--fast-ms", type=float, default=8.0)
    parser.add_argument("--strong-ms", type=float, default=25.0)
    parser.add_argument(
        "--orchestrate",
        action="store_true",
        help="Route + MCP local loop + premium apply gate (scripted reviewer)",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Directory for JSONL/JSON summaries (gitignored eval-runs/)",
    )
    args = parser.parse_args()
    if args.orchestrate:
        results = asyncio.run(
            run_orchestrated_campaign(
                backend=args.backend,
                profile=args.profile,
                job_ids=args.job_ids,
                fast_ms=args.fast_ms,
                strong_ms=args.strong_ms,
            )
        )
        print(format_orchestrated(results))
        if args.out:
            dest = Path(args.out)
            dest.mkdir(parents=True, exist_ok=True)
            payload = [
                {
                    "job": item.job,
                    "delegated": item.delegated,
                    "route": item.route_reason,
                    "outcome": item.outcome,
                    "applied": item.applied,
                    "source": item.apply_source,
                    "models": list(item.local_models),
                    "review": item.review_decision,
                }
                for item in results
            ]
            (dest / "orchestrated.json").write_text(
                json.dumps(payload, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"wrote {dest / 'orchestrated.json'}")
        raise SystemExit(0 if results else 1)
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
