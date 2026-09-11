#!/usr/bin/env python3
"""Score the committed corpus. Fixtures need no GPU. --live needs Ollama."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
LIVE_STATUS_PATH = ROOT / "eval-runs" / "live-status.json"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from local_coding_slm.eval.cases import (  # noqa: E402
    CASES,
    CASES_BY_ID,
    FIXTURES,
    SEED_CASE_IDS,
)
from local_coding_slm.eval.cases_harder import HARDER_CASE_IDS  # noqa: E402
from local_coding_slm.eval.score import score_candidate  # noqa: E402

SUITE_CASE_IDS = {
    "all": None,
    "seed": set(SEED_CASE_IDS),
    "harder": set(HARDER_CASE_IDS),
}


def _print_result(label: str, result: object) -> None:
    passed = getattr(result, "passed")
    mark = "PASS" if passed else "FAIL"
    first = getattr(result, "first_failure")
    extra = ""
    if first is not None:
        extra = f" stop={first.name} ({first.message})"
    print(f"{mark} {label}{extra}")
    for layer in getattr(result, "layers"):
        print(f"  {layer.status:4} {layer.name}: {layer.message}")


def _write_live_status(*, skipped: bool) -> None:
    LIVE_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    LIVE_STATUS_PATH.write_text(
        json.dumps({"skipped": skipped}) + "\n",
        encoding="utf-8",
    )


def _wanted(case_id: str, suite: str, only: str | None) -> bool:
    if only and case_id != only:
        return False
    allowed = SUITE_CASE_IDS[suite]
    return allowed is None or case_id in allowed


def _run_fixtures(case_id: str | None, suite: str) -> int:
    failed = 0
    ran = 0
    for fixture in FIXTURES:
        if not _wanted(fixture.case_id, suite, case_id):
            continue
        ran += 1
        case = CASES_BY_ID[fixture.case_id]
        result = score_candidate(fixture.text, case)
        ok = result.passed == fixture.expect_pass
        if fixture.expect_first:
            failure = result.first_failure
            ok = ok and failure is not None and failure.name == fixture.expect_first
        else:
            ok = ok and result.passed
        mark = "OK" if ok else "WRONG"
        stop = ""
        first = result.first_failure
        if first is not None:
            stop = f" stop={first.name}"
        print(f"{mark} fixture:{fixture.name} candidate_pass={result.passed}{stop}")
        for layer in result.layers:
            print(f"  {layer.status:4} {layer.name}: {layer.message}")
        if not ok:
            print(f"  expected pass={fixture.expect_pass} first={fixture.expect_first}")
            failed += 1
    if ran == 0:
        print("no fixtures matched")
        return 1
    return failed


async def _run_live(
    case_id: str | None, model: str, suite: str, *, require_live: bool
) -> int:
    from local_coding_slm.ollama_client import OllamaSettings, is_reachable
    from local_coding_slm.server import _load_dotenv

    _load_dotenv()
    settings = OllamaSettings.from_env()
    if not is_reachable(settings):
        _write_live_status(skipped=True)
        print(
            f"SKIP live: Ollama unreachable at {settings.host_label()} "
            "(offline fixtures still pass; this is not a model-quality fail)"
        )
        return 2 if require_live else 0
    _write_live_status(skipped=False)

    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SRC / "local_coding_slm" / "server.py")],
        env=env,
        cwd=str(ROOT),
    )
    failed = 0
    selected = [
        case for case in CASES if _wanted(case.id, suite, case_id)
    ]
    if not selected:
        print("no live cases matched")
        return 1
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            for case in selected:
                payload = {
                    "task": case.task,
                    "files": list(case.files),
                    "language": case.language,
                    "model": model,
                    "max_tokens": case.max_tokens,
                }
                if case.style:
                    payload["style"] = case.style
                tool = await session.call_tool(case.tool, payload)
                text = "".join(
                    block.text
                    for block in tool.content
                    if getattr(block, "text", None)
                )
                result = score_candidate(text, case)
                _print_result(f"live:{case.id} model={model}", result)
                if not result.passed:
                    failed += 1
                    print("  candidate:")
                    print(text[:1200])
    return failed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Call real Ollama via stdio MCP")
    parser.add_argument(
        "--require-live",
        action="store_true",
        help="Same as --live, but exit 2 when Ollama is down instead of skip-0.",
    )
    parser.add_argument("--model", choices=("fast", "strong"), default="fast")
    parser.add_argument("--case", dest="case_id", default=None)
    parser.add_argument(
        "--suite",
        choices=tuple(SUITE_CASE_IDS),
        default="all",
        help="Fixture / live subset. harder = Phase 3 multi-file behavior cases.",
    )
    args = parser.parse_args()
    if args.live or args.require_live:
        raise SystemExit(
            asyncio.run(
                _run_live(
                    args.case_id,
                    args.model,
                    args.suite,
                    require_live=args.require_live,
                )
            )
        )
    failed = _run_fixtures(args.case_id, args.suite)
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
