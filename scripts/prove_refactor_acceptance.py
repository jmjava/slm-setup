#!/usr/bin/env python3
"""Run a semantic local_refactor check against the configured Ollama runtime."""

from __future__ import annotations

import argparse
import asyncio
import ast
import os
import re
import sys
from pathlib import Path
from typing import Callable, cast

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from local_coding_slm.server import _load_dotenv  # noqa: E402

_load_dotenv()

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

SOURCE = """\
def normalize_user(name: str, email: str) -> tuple[str, str]:
    cleaned_name = " ".join(name.strip().split())
    cleaned_email = " ".join(email.strip().split()).lower()
    return cleaned_name, cleaned_email
"""

CASES = [
    ("  Ada   Lovelace ", " ADA@EXAMPLE.COM ", ("Ada Lovelace", "ada@example.com")),
    ("\tGrace\nHopper", " G@EXAMPLE.COM ", ("Grace Hopper", "g@example.com")),
    ("", "", ("", "")),
]


def _extract_python(text: str) -> str:
    match = re.search(r"```(?:python)?\s*\n(.*?)```", text, flags=re.DOTALL)
    if not match:
        raise ValueError("local_refactor did not return one fenced Python file")
    return match.group(1).strip() + "\n"


def _verify_refactor(code: str) -> None:
    tree = ast.parse(code)
    function_names = {
        node.name for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    if "_normalize_whitespace" not in function_names:
        raise AssertionError("expected extracted helper _normalize_whitespace")

    namespace: dict[str, object] = {}
    exec(compile(tree, "generated_user_text.py", "exec"), namespace)
    normalize = namespace.get("normalize_user")
    if not callable(normalize):
        raise AssertionError("generated module has no callable normalize_user")

    typed_normalize = cast(Callable[[str, str], tuple[str, str]], normalize)
    for name, email, expected in CASES:
        actual = typed_normalize(name, email)
        if actual != expected:
            raise AssertionError(
                f"behavior changed for {name!r}, {email!r}: "
                f"expected {expected!r}, got {actual!r}"
            )


async def _run(model: str) -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SRC / "local_coding_slm" / "server.py")],
        env=env,
        cwd=str(ROOT),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "local_refactor",
                {
                    "task": (
                        "Extract the repeated whitespace normalization into a "
                        "module-level (top-level) private helper named "
                        "_normalize_whitespace. Preserve the exact behavior "
                        "and public function signature. Return one complete "
                        "fenced Python file and no prose."
                    ),
                    "files": [{"path": "user_text.py", "content": SOURCE}],
                    "language": "python",
                    "style": "Keep the code minimal and preserve type hints.",
                    "model": model,
                    "max_tokens": 500,
                },
            )
    text = "".join(
        block.text for block in result.content if getattr(block, "text", None)
    )
    if text.startswith("ERROR:"):
        raise RuntimeError(text)
    try:
        code = _extract_python(text)
    except Exception:
        print("Generated response failed output-format acceptance:")
        print(text)
        raise
    try:
        _verify_refactor(code)
    except Exception:
        print("Generated candidate failed acceptance:")
        print(code)
        raise
    print(
        f"PASS live local_refactor model={model}: "
        "helper extracted and behavior preserved"
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=("fast", "strong"), default="fast")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args.model)))


if __name__ == "__main__":
    main()
