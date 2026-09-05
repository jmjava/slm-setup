"""HTTP client for a private Ollama instance. Talks only to OLLAMA_BASE_URL."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

DEFAULT_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_FAST_MODEL = "qwen3.5:9b"
DEFAULT_STRONG_MODEL = "devstral-small-2"
DEFAULT_NUM_CTX = 16384
MAX_TOKENS_CAP = 4096
FAST_TIMEOUT_S = 120
STRONG_TIMEOUT_S = 300


class OllamaError(Exception):
    """Structured failure talking to Ollama."""


@dataclass(frozen=True)
class OllamaSettings:
    base_url: str
    fast_model: str
    strong_model: str
    num_ctx: int

    @classmethod
    def from_env(cls) -> "OllamaSettings":
        return cls(
            base_url=os.environ.get("OLLAMA_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            fast_model=os.environ.get("OLLAMA_FAST_MODEL", DEFAULT_FAST_MODEL),
            strong_model=os.environ.get("OLLAMA_STRONG_MODEL", DEFAULT_STRONG_MODEL),
            num_ctx=int(os.environ.get("OLLAMA_NUM_CTX", str(DEFAULT_NUM_CTX))),
        )

    def resolve_model(self, model: str | None) -> str:
        choice = (model or "fast").strip().lower()
        if choice == "strong":
            return self.strong_model
        if choice == "fast":
            return self.fast_model
        raise OllamaError(f"model must be 'fast' or 'strong', got {model!r}")

    def timeout_s(self, model: str | None) -> int:
        choice = (model or "fast").strip().lower()
        return STRONG_TIMEOUT_S if choice == "strong" else FAST_TIMEOUT_S

    def host_label(self) -> str:
        parsed = urlparse(self.base_url)
        return parsed.hostname or "unknown"


def _post_json(url: str, payload: dict[str, Any], timeout_s: int) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise OllamaError(f"Ollama HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise OllamaError(f"Ollama unreachable: {exc.reason}") from exc
    except TimeoutError as exc:
        raise OllamaError(f"Ollama timed out after {timeout_s}s") from exc
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise OllamaError("Ollama returned non-JSON") from exc
    if not isinstance(parsed, dict):
        raise OllamaError("Ollama returned unexpected JSON")
    return parsed


def _get_json(url: str, timeout_s: int) -> dict[str, Any]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise OllamaError(f"Ollama HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise OllamaError(f"Ollama unreachable: {exc.reason}") from exc
    except TimeoutError as exc:
        raise OllamaError(f"Ollama timed out after {timeout_s}s") from exc
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        raise OllamaError("Ollama returned unexpected JSON")
    return parsed


def list_model_names(settings: OllamaSettings | None = None) -> list[str]:
    settings = settings or OllamaSettings.from_env()
    payload = _get_json(urljoin(settings.base_url + "/", "api/tags"), timeout_s=15)
    models = payload.get("models") or []
    names: list[str] = []
    for item in models:
        if isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
    return names


def status_report(settings: OllamaSettings | None = None) -> str:
    settings = settings or OllamaSettings.from_env()
    try:
        names = list_model_names(settings)
    except OllamaError as exc:
        return (
            f"host={settings.host_label()} ok=false error={exc} "
            f"fast={settings.fast_model} strong={settings.strong_model}"
        )
    have_fast = any(settings.fast_model in n for n in names)
    have_strong = any(settings.strong_model in n for n in names)
    return (
        f"host={settings.host_label()} ok=true "
        f"fast={settings.fast_model} present={have_fast} "
        f"strong={settings.strong_model} present={have_strong} "
        f"models={len(names)}"
    )


def chat(
    system: str,
    user: str,
    model: str | None = "fast",
    max_tokens: int | None = None,
    settings: OllamaSettings | None = None,
) -> str:
    settings = settings or OllamaSettings.from_env()
    tag = settings.resolve_model(model)
    timeout_s = settings.timeout_s(model)
    num_predict = MAX_TOKENS_CAP
    if max_tokens is not None:
        num_predict = max(1, min(int(max_tokens), MAX_TOKENS_CAP))
    payload = {
        "model": tag,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {
            "num_ctx": settings.num_ctx,
            "num_predict": num_predict,
        },
    }
    result = _post_json(
        urljoin(settings.base_url + "/", "api/chat"),
        payload,
        timeout_s=timeout_s,
    )
    message = result.get("message") or {}
    content = message.get("content") if isinstance(message, dict) else None
    if not content:
        raise OllamaError("Ollama returned an empty message")
    return str(content)


def format_user_task(
    task: str,
    files: list[dict[str, str]] | None = None,
    language: str | None = None,
    style: str | None = None,
) -> str:
    parts = [task.strip()]
    if language:
        parts.append(f"Language hint: {language}")
    if style:
        parts.append(f"Style: {style}")
    if files:
        parts.append("Files:")
        for item in files:
            path = item.get("path") or "unknown"
            content = item.get("content") or ""
            parts.append(f"--- {path} ---\n{content}")
    return "\n\n".join(parts)
