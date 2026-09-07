"""Refuse unsafe or oversized snippets before they reach Ollama.

Used by the MCP server (defense in depth) and by eval routing. This is
not a classifier: it only looks at file names, size, and a few secret
shapes. Code that merely mentions ``password`` is allowed.
"""

from __future__ import annotations

from collections.abc import Sequence

MAX_FILES = 12
MAX_BYTES = 120_000
MAX_TOKENS = 8192

_PRIVATE_KEY_MARKERS = (
    "-----BEGIN OPENSSH PRIVATE KEY-----",
    "-----BEGIN RSA PRIVATE KEY-----",
    "-----BEGIN EC PRIVATE KEY-----",
    "-----BEGIN PRIVATE KEY-----",
)
_TOKEN_PREFIXES = ("ghp_", "github_pat_", "sk-proj-", "sk-ant-")


def inspect_payload(
    files: Sequence[dict[str, str]] | None,
    *,
    max_tokens: int | None = None,
) -> str | None:
    """Return a stable reason string, or None if the payload may be sent."""
    if max_tokens is not None and max_tokens > MAX_TOKENS:
        return "max_tokens_too_large"
    items = list(files or ())
    if len(items) > MAX_FILES:
        return "too_many_files"
    total = 0
    for item in items:
        path = str(item.get("path") or "")
        content = str(item.get("content") or "")
        total += len(content)
        name_reason = _secret_path(path)
        if name_reason:
            return name_reason
        content_reason = _secret_content(content)
        if content_reason:
            return content_reason
    if total > MAX_BYTES:
        return "payload_too_large"
    return None


def refusal_message(reason: str) -> str:
    return f"ERROR: refused to send payload to local model ({reason})"


def _secret_path(path: str) -> str | None:
    name = path.replace("\\", "/").rsplit("/", 1)[-1].lower()
    if name == ".env.example":
        return None
    if name == ".env" or name.startswith(".env."):
        return "secrets_file"
    if name in {"credentials.json", "id_rsa", "id_rsa.pub"}:
        return "secrets_file"
    return None


def _secret_content(content: str) -> str | None:
    if any(marker in content for marker in _PRIVATE_KEY_MARKERS):
        return "secret_content"
    lowered = content.lower()
    if "aws_secret_access_key=" in lowered:
        return "secret_content"
    for prefix in _TOKEN_PREFIXES:
        if prefix in content:
            return "secret_content"
    return None
