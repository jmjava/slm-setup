#!/usr/bin/env python3
"""stdio MCP server: premium agent → private Ollama SLM."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Literal

# Allow `python src/local_coding_slm/server.py` without installing the package.
_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from local_coding_slm.envfile import merge_dotenv  # noqa: E402
from local_coding_slm.ollama_client import (  # noqa: E402
    OllamaError,
    chat,
    format_user_task,
    status_report,
)
from local_coding_slm.prompts import SYSTEM_PROMPTS  # noqa: E402


def _load_dotenv() -> None:
    """Load repo-root .env. Empty interpolated env vars do not win."""
    here = Path(__file__).resolve()
    candidates = [
        Path.cwd() / ".env",
        here.parents[2] / ".env",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        merge_dotenv(path.read_text(encoding="utf-8").splitlines(), os.environ)
        break


_load_dotenv()

from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("local-coding-slm")

ModelChoice = Literal["fast", "strong"]


def _run_tool(
    name: str,
    task: str,
    files: list[dict[str, str]] | None,
    language: str | None,
    style: str | None,
    model: ModelChoice,
    max_tokens: int | None,
) -> str:
    if not task or not task.strip():
        return "ERROR: task is required"
    user = format_user_task(task, files=files, language=language, style=style)
    try:
        return chat(
            SYSTEM_PROMPTS[name],
            user,
            model=model,
            max_tokens=max_tokens,
        )
    except OllamaError as exc:
        return f"ERROR: {exc}"


@mcp.tool()
def local_status() -> str:
    """Health of Ollama and whether the configured fast/strong models are present."""
    return status_report()


@mcp.tool()
def local_code(
    task: str,
    files: list[dict[str, str]] | None = None,
    language: str | None = None,
    style: str | None = None,
    model: ModelChoice = "fast",
    max_tokens: int | None = None,
) -> str:
    """Generate new code for a well-specified unit of work."""
    return _run_tool("local_code", task, files, language, style, model, max_tokens)


@mcp.tool()
def local_refactor(
    task: str,
    files: list[dict[str, str]] | None = None,
    language: str | None = None,
    style: str | None = None,
    model: ModelChoice = "fast",
    max_tokens: int | None = None,
) -> str:
    """Mechanical, localized rewrite. Return a diff or fenced files."""
    return _run_tool("local_refactor", task, files, language, style, model, max_tokens)


@mcp.tool()
def local_generate_tests(
    task: str,
    files: list[dict[str, str]] | None = None,
    language: str | None = None,
    style: str | None = None,
    model: ModelChoice = "fast",
    max_tokens: int | None = None,
) -> str:
    """Generate unit or integration tests only. Do not change production code."""
    return _run_tool(
        "local_generate_tests", task, files, language, style, model, max_tokens
    )


@mcp.tool()
def local_explain(
    task: str,
    files: list[dict[str, str]] | None = None,
    language: str | None = None,
    style: str | None = None,
    model: ModelChoice = "fast",
    max_tokens: int | None = None,
) -> str:
    """Explain a snippet or flow."""
    return _run_tool("local_explain", task, files, language, style, model, max_tokens)


@mcp.tool()
def local_review(
    task: str,
    files: list[dict[str, str]] | None = None,
    language: str | None = None,
    style: str | None = None,
    model: ModelChoice = "fast",
    max_tokens: int | None = None,
) -> str:
    """Cheap first-pass review for obvious null, auth, and test gaps."""
    return _run_tool("local_review", task, files, language, style, model, max_tokens)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
