#!/usr/bin/env python3
"""Run A5/A6 against the local stdio MCP server. Loads repo-root .env."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from local_coding_slm.server import _load_dotenv  # noqa: E402

_load_dotenv()

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

TINY_FN = "def add(a: int, b: int) -> int:\n    return a + b\n"


async def _run() -> int:
    python = sys.executable
    server = SRC / "local_coding_slm" / "server.py"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    params = StdioServerParameters(
        command=python,
        args=[str(server)],
        env=env,
        cwd=str(ROOT),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            names = sorted(t.name for t in listed.tools)
            print("TOOLS", " ".join(names))
            expected = {
                "local_code",
                "local_explain",
                "local_generate_tests",
                "local_refactor",
                "local_review",
                "local_status",
            }
            missing = expected - set(names)
            if missing:
                print("FAIL missing tools:", ", ".join(sorted(missing)))
                return 1

            status = await session.call_tool("local_status", {})
            status_text = "".join(
                block.text for block in status.content if getattr(block, "text", None)
            )
            print("A5", status_text)
            if "ok=true" not in status_text or "fast=" not in status_text:
                print("FAIL A5 local_status")
                return 1

            tests = await session.call_tool(
                "local_generate_tests",
                {
                    "task": (
                        "Write pytest unit tests for add(). Cover two positives "
                        "and one negative. Return a single fenced file."
                    ),
                    "files": [{"path": "add.py", "content": TINY_FN}],
                    "language": "python",
                    "style": "pytest",
                    "model": "fast",
                    "max_tokens": 400,
                },
            )
            tests_text = "".join(
                block.text for block in tests.content if getattr(block, "text", None)
            )
            print("A6")
            print(tests_text)
            lowered = tests_text.lower()
            if tests_text.startswith("ERROR:") or "def test" not in lowered:
                print("FAIL A6 local_generate_tests")
                return 1
    print("PASS A5 A6")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
