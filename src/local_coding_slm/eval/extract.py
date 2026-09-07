"""Parse MCP tool text into files. No network, no model calls."""

from __future__ import annotations

import re
from dataclasses import dataclass

FENCE_RE = re.compile(r"```([^\n]*)\n(.*?)```", flags=re.DOTALL)
PATH_COMMENT_RE = re.compile(
    r"^(?:#|//)\s*(?:(?:file|path)\s*:\s*)?([\w./\\-]+\.[\w]+)\s*$",
    flags=re.IGNORECASE,
)
DIFF_PATH_RE = re.compile(r"^\+\+\+\s+(?:b/)?(.+)$", flags=re.MULTILINE)


class TransportError(ValueError):
    """Candidate is an MCP/Ollama error payload, not generated code."""


@dataclass(frozen=True)
class ExtractedFile:
    path: str
    content: str
    kind: str  # fence | diff


def extract_files(text: str) -> list[ExtractedFile]:
    """Turn a tool response into path/content pairs.

    Transport errors raise ``TransportError``. A parseable unified diff with
    no fences is returned as kind ``diff``. Executable scoring (AST / exec)
    requires fenced files.
    """
    raw = (text or "").strip()
    if not raw:
        raise ValueError("empty tool response")
    if raw.startswith("ERROR:"):
        raise TransportError(raw.splitlines()[0][:240])

    fences = _fenced_files(raw)
    if fences:
        return fences
    diff = _unified_diff(raw)
    if diff:
        return [diff]
    raise ValueError("no markdown fenced file or unified diff found")


def _fenced_files(text: str) -> list[ExtractedFile]:
    found: list[ExtractedFile] = []
    for info, body in FENCE_RE.findall(text):
        content = body.strip() + "\n"
        path = _path_from_info(info) or _path_from_first_comment(body) or "unknown"
        found.append(ExtractedFile(path=path, content=content, kind="fence"))
    return found


def _path_from_info(info: str) -> str | None:
    token = (info or "").strip().strip('"').strip("'")
    if not token:
        return None
    # ```python, ```py, ```json — language tags, not paths
    if token.lower() in {"python", "py", "diff", "text", "json", "md", "markdown"}:
        return None
    if token.lower().startswith("python ") or token.lower().startswith("py "):
        rest = token.split(None, 1)[1].strip().strip('"').strip("'")
        return rest or None
    if "." in token or "/" in token:
        return token.split()[0]
    return None


def _path_from_first_comment(body: str) -> str | None:
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = PATH_COMMENT_RE.match(stripped)
        return match.group(1) if match else None
    return None


def _unified_diff(text: str) -> ExtractedFile | None:
    if "\n+++" not in text and not text.startswith("+++"):
        return None
    if "@@" not in text:
        return None
    match = DIFF_PATH_RE.search(text)
    path = match.group(1).strip() if match else "unknown"
    return ExtractedFile(path=path, content=text if text.endswith("\n") else text + "\n", kind="diff")
