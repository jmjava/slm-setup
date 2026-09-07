#!/usr/bin/env python3
"""Score the committed corpus. Fixtures need no GPU. --live needs Ollama."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from local_coding_slm.eval.cases import CASES, CASES_BY_ID, FIXTURES  # noqa: E402
from local_coding_slm.eval.score import score_candidate  # noqa: E402


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


def _run_fixtures(case_id: str | None) -> int:
    failed = 0
    for fixture in FIXTURES:
        if case_id and fixture.case_id != case_id:
            continue
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
    return failed


async def _run_live(case_id: str | None, model: str) -> int:
    from local_coding_slm.server import _load_dotenv

    _load_dotenv()
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
    selected = [case for case in CASES if case_id is None or case.id == case_id]
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            for case in selected:
                payload = {
                    "task": case.task,
                    "files": list(case.files),
                    "language": case.language,
                    "model": model,
                    "max_tokens": 700,
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
    parser.add_argument("--model", choices=("fast", "strong"), default="fast")
    parser.add_argument("--case", dest="case_id", default=None)
    args = parser.parse_args()
    if args.live:
        raise SystemExit(asyncio.run(_run_live(args.case_id, args.model)))
    failed = _run_fixtures(args.case_id)
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
