"""Loopback Ollama stand-in. Scripted replies, real HTTP, 127.0.0.1 only."""

from __future__ import annotations

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any
from urllib.parse import urlparse

from local_coding_slm.eval.cases import (
    CASES,
    GOLDEN_FOR_CASE,
    MULTI_FILE_PARTIAL,
    TEST_ADD_SHAPE_ONLY,
    WHITESPACE_NESTED,
    WHITESPACE_NO_FENCE,
)
from local_coding_slm.eval.cases_extended import OBSERVED_FIRST
from local_coding_slm.ollama_client import DEFAULT_FAST_MODEL, DEFAULT_STRONG_MODEL


def infer_case_id(user: str) -> str | None:
    matches = [case for case in CASES if case.task and case.task in user]
    if not matches:
        return None
    return max(matches, key=lambda case: len(case.task)).id


def scripted_content(case_id: str, model_choice: str, visit: int, profile: str) -> str:
    """Deterministic worker. Not a claim about live model quality."""
    golden = GOLDEN_FOR_CASE[case_id]
    if profile == "golden":
        return golden
    if profile != "observed":
        raise ValueError(f"unknown stub profile {profile!r}")
    # These stay wrong for every fast call so the policy must escalate to strong.
    if model_choice == "fast" and case_id == "whitespace_extract_vague":
        return WHITESPACE_NESTED
    if model_choice == "fast" and case_id == "test_add_execute":
        return TEST_ADD_SHAPE_ONLY
    first_fail = {
        "whitespace_extract": WHITESPACE_NO_FENCE,
        "multi_file_rename": MULTI_FILE_PARTIAL,
        **OBSERVED_FIRST,
    }
    if model_choice == "fast" and visit == 1 and case_id in first_fail:
        return first_fail[case_id]
    return golden


class StubState:
    def __init__(self, profile: str, fast_ms: float, strong_ms: float) -> None:
        self.profile = profile
        self.fast_ms = fast_ms
        self.strong_ms = strong_ms
        self.visits: dict[tuple[str, str], int] = {}
        self.calls = 0

    def reply(self, model_tag: str, user: str) -> str:
        case_id = infer_case_id(user) or "unknown"
        choice = "strong" if model_tag == DEFAULT_STRONG_MODEL else "fast"
        key = (case_id, choice)
        self.visits[key] = self.visits.get(key, 0) + 1
        self.calls += 1
        delay = self.strong_ms if choice == "strong" else self.fast_ms
        if delay > 0:
            time.sleep(delay / 1000.0)
        if case_id == "unknown":
            return "I cannot match that task."
        return scripted_content(case_id, choice, self.visits[key], self.profile)


def _handler(state: StubState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def _send(self, code: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path.rstrip("/") == "/api/tags":
                self._send(
                    200,
                    {
                        "models": [
                            {"name": DEFAULT_FAST_MODEL},
                            {"name": DEFAULT_STRONG_MODEL},
                        ]
                    },
                )
                return
            self._send(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            length = int(self.headers.get("Content-Length") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                self._send(400, {"error": "bad json"})
                return
            if path.rstrip("/") != "/api/chat":
                self._send(404, {"error": "not found"})
                return
            model = str(payload.get("model") or "")
            messages = payload.get("messages") or []
            user = ""
            for item in messages:
                if isinstance(item, dict) and item.get("role") == "user":
                    user = str(item.get("content") or "")
            content = state.reply(model, user)
            self._send(200, {"message": {"role": "assistant", "content": content}})

    return Handler


class StubOllama:
    """Threading loopback server. Bind is always 127.0.0.1."""

    def __init__(
        self,
        profile: str = "golden",
        fast_ms: float = 8.0,
        strong_ms: float = 25.0,
    ) -> None:
        self.state = StubState(profile=profile, fast_ms=fast_ms, strong_ms=strong_ms)
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), _handler(self.state))
        self._thread: Thread | None = None

    @property
    def base_url(self) -> str:
        host, port = self._httpd.server_address[:2]
        return f"http://{host}:{port}"

    def __enter__(self) -> "StubOllama":
        self._thread = Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *args: object) -> None:
        self._httpd.shutdown()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._httpd.server_close()
