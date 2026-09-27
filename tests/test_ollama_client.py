import json
import os
import socket
import threading
import unittest
from unittest.mock import patch
from urllib.error import URLError

from local_coding_slm.ollama_client import (
    ALLOW_UNOFFICIAL_TAGS_ENV,
    OllamaError,
    OllamaSettings,
    chat,
    format_user_task,
    is_reachable,
    list_model_names,
    status_report,
)
from local_coding_slm.safety import OFFICIAL_LIBRARY_TAGS


class _FakeResp:
    def __init__(self, payload: dict):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, *args: object) -> None:
        return None


class SettingsTests(unittest.TestCase):
    def test_resolve_model(self) -> None:
        settings = OllamaSettings(
            base_url="http://127.0.0.1:11434",
            fast_model="qwen3.5:9b",
            strong_model="devstral-small-2",
            num_ctx=16384,
        )
        self.assertEqual(settings.resolve_model("fast"), "qwen3.5:9b")
        self.assertEqual(settings.resolve_model("strong"), "devstral-small-2")
        self.assertEqual(settings.resolve_model(None), "qwen3.5:9b")
        with self.assertRaises(OllamaError):
            settings.resolve_model("medium")

    def test_resolve_model_rejects_off_allowlist(self) -> None:
        """Leftover #13: unofficial tags must not reach Ollama without a hatch."""
        settings = OllamaSettings(
            base_url="http://127.0.0.1:11434",
            fast_model="sketchy-backdoor-gguf:q4",
            strong_model="devstral-small-2",
            num_ctx=16384,
        )
        with self.assertRaises(OllamaError) as raised:
            settings.resolve_model("fast")
        self.assertIn("unofficial_model_tag", str(raised.exception))
        self.assertIn("sketchy-backdoor-gguf:q4", str(raised.exception))

    def test_resolve_model_allows_off_allowlist_with_escape_hatch(self) -> None:
        """Leftover #13: only an explicit hatch may resolve an unofficial tag."""
        settings = OllamaSettings(
            base_url="http://127.0.0.1:11434",
            fast_model="sketchy-backdoor-gguf:q4",
            strong_model="devstral-small-2",
            num_ctx=16384,
            allow_unofficial=True,
        )
        self.assertEqual(settings.resolve_model("fast"), "sketchy-backdoor-gguf:q4")

    def test_resolve_model_from_env_escape_hatch(self) -> None:
        env = {
            "OLLAMA_FAST_MODEL": "sketchy-backdoor-gguf:q4",
            "OLLAMA_STRONG_MODEL": "devstral-small-2",
            ALLOW_UNOFFICIAL_TAGS_ENV: "1",
        }
        with patch.dict(os.environ, env, clear=False):
            settings = OllamaSettings.from_env()
        self.assertTrue(settings.allow_unofficial)
        self.assertEqual(settings.resolve_model("fast"), "sketchy-backdoor-gguf:q4")

    def test_resolve_model_from_env_rejects_off_allowlist(self) -> None:
        env = {
            "OLLAMA_FAST_MODEL": "sketchy-backdoor-gguf:q4",
            "OLLAMA_STRONG_MODEL": "devstral-small-2",
            ALLOW_UNOFFICIAL_TAGS_ENV: "0",
        }
        with patch.dict(os.environ, env, clear=False):
            settings = OllamaSettings.from_env()
        self.assertFalse(settings.allow_unofficial)
        with self.assertRaises(OllamaError) as raised:
            settings.resolve_model("fast")
        self.assertIn("unofficial_model_tag", str(raised.exception))

    def test_allowlist_length_changes_resolve_model_accept_reject(self) -> None:
        extra = "brand-new-coder:7b"
        extra_settings = OllamaSettings(
            base_url="http://127.0.0.1:11434",
            fast_model=extra,
            strong_model="devstral-small-2",
            num_ctx=16384,
        )
        with self.assertRaises(OllamaError) as raised:
            extra_settings.resolve_model("fast")
        self.assertIn("unofficial_model_tag", str(raised.exception))
        lengthened = OFFICIAL_LIBRARY_TAGS | {extra}
        with patch("local_coding_slm.safety.OFFICIAL_LIBRARY_TAGS", lengthened):
            self.assertEqual(extra_settings.resolve_model("fast"), extra)
        starter = OllamaSettings(
            base_url="http://127.0.0.1:11434",
            fast_model="qwen3.5:9b",
            strong_model="devstral-small-2",
            num_ctx=16384,
        )
        shortened = OFFICIAL_LIBRARY_TAGS - {"qwen3.5:9b"}
        with patch("local_coding_slm.safety.OFFICIAL_LIBRARY_TAGS", shortened):
            with self.assertRaises(OllamaError) as shortened_raised:
                starter.resolve_model("fast")
            self.assertIn("unofficial_model_tag", str(shortened_raised.exception))
        self.assertEqual(starter.resolve_model("fast"), "qwen3.5:9b")

    def test_host_label_is_hostname_only(self) -> None:
        settings = OllamaSettings(
            base_url="http://127.0.0.1:11435",
            fast_model="qwen3.5:9b",
            strong_model="devstral-small-2",
            num_ctx=16384,
        )
        self.assertEqual(settings.host_label(), "127.0.0.1")


class ClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = OllamaSettings(
            base_url="http://127.0.0.1:11434",
            fast_model="qwen3.5:9b",
            strong_model="devstral-small-2",
            num_ctx=4096,
        )

    def test_list_model_names(self) -> None:
        payload = {
            "models": [
                {"name": "qwen3.5:9b"},
                {"name": "devstral-small-2:latest"},
            ]
        }
        with patch(
            "local_coding_slm.ollama_client._urlopen",
            return_value=_FakeResp(payload),
        ):
            names = list_model_names(self.settings)
        self.assertEqual(names, ["qwen3.5:9b", "devstral-small-2:latest"])

    def test_status_report_marks_present_models(self) -> None:
        payload = {"models": [{"name": "qwen3.5:9b"}]}
        with patch(
            "local_coding_slm.ollama_client._urlopen",
            return_value=_FakeResp(payload),
        ):
            report = status_report(self.settings)
        self.assertIn("host=127.0.0.1", report)
        self.assertIn("fast=qwen3.5:9b present=True", report)
        self.assertIn("strong=devstral-small-2 present=False", report)

    def test_chat_returns_message_content(self) -> None:
        payload = {"message": {"content": "def ping(): return True"}}
        with patch(
            "local_coding_slm.ollama_client._urlopen",
            return_value=_FakeResp(payload),
        ) as mocked:
            text = chat("sys", "write ping", model="fast", settings=self.settings)
        self.assertEqual(text, "def ping(): return True")
        req = mocked.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        self.assertFalse(body["stream"])
        self.assertEqual(body["model"], "qwen3.5:9b")

    def test_chat_num_predict_equals_requested(self) -> None:
        payload = {"message": {"content": "ok"}}
        with patch(
            "local_coding_slm.ollama_client._urlopen",
            return_value=_FakeResp(payload),
        ) as mocked:
            chat(
                "sys",
                "write ping",
                model="fast",
                max_tokens=2048,
                settings=self.settings,
            )
        req = mocked.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(body["options"]["num_predict"], 2048)

    def test_chat_max_tokens_above_cap_raises_without_post(self) -> None:
        with patch(
            "local_coding_slm.ollama_client._urlopen",
        ) as mocked:
            with self.assertRaises(OllamaError) as raised:
                chat(
                    "sys",
                    "write ping",
                    model="fast",
                    max_tokens=8192,
                    settings=self.settings,
                )
        self.assertIn("max_tokens_too_large", str(raised.exception))
        mocked.assert_not_called()

    def test_chat_rejects_unofficial_tag_without_post(self) -> None:
        settings = OllamaSettings(
            base_url="http://127.0.0.1:11434",
            fast_model="sketchy-backdoor-gguf:q4",
            strong_model="devstral-small-2",
            num_ctx=4096,
        )
        with patch(
            "local_coding_slm.ollama_client._urlopen",
        ) as mocked:
            with self.assertRaises(OllamaError) as raised:
                chat("sys", "write ping", model="fast", settings=settings)
        self.assertIn("unofficial_model_tag", str(raised.exception))
        mocked.assert_not_called()

    def test_chat_omitted_max_tokens_posts_cap_in_body(self) -> None:
        """Leftover #8: default clamp is options.num_predict, not payload.MAX_TOKENS."""
        payload = {"message": {"content": "ok"}}
        with patch(
            "local_coding_slm.ollama_client._urlopen",
            return_value=_FakeResp(payload),
        ) as mocked:
            chat("sys", "write ping", model="fast", settings=self.settings)
        req = mocked.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(body["options"]["num_predict"], 4096)

    def test_chat_max_tokens_zero_posts_floor_clamp_in_body(self) -> None:
        """Leftover #8: max(1, requested) must show up in the POST body."""
        payload = {"message": {"content": "ok"}}
        with patch(
            "local_coding_slm.ollama_client._urlopen",
            return_value=_FakeResp(payload),
        ) as mocked:
            chat(
                "sys",
                "write ping",
                model="fast",
                max_tokens=0,
                settings=self.settings,
            )
        req = mocked.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(body["options"]["num_predict"], 1)
        self.assertNotEqual(body["options"]["num_predict"], 0)

    def test_chat_max_tokens_9000_does_not_post_clamped_body(self) -> None:
        """Leftover #8: inspect_payload(9000) is not enough; client must not POST 4096."""
        with patch(
            "local_coding_slm.ollama_client._urlopen",
        ) as mocked:
            with self.assertRaises(OllamaError) as raised:
                chat(
                    "sys",
                    "write ping",
                    model="fast",
                    max_tokens=9000,
                    settings=self.settings,
                )
        self.assertIn("max_tokens_too_large", str(raised.exception))
        mocked.assert_not_called()

    def test_unreachable_becomes_ollama_error(self) -> None:
        with patch(
            "local_coding_slm.ollama_client._urlopen",
            side_effect=URLError("down"),
        ):
            with self.assertRaises(OllamaError):
                list_model_names(self.settings)

    def test_is_reachable_true_on_tags(self) -> None:
        with patch(
            "local_coding_slm.ollama_client._urlopen",
            return_value=_FakeResp({"models": []}),
        ):
            self.assertTrue(is_reachable(self.settings))

    def test_is_reachable_false_when_down(self) -> None:
        with patch(
            "local_coding_slm.ollama_client._urlopen",
            side_effect=URLError("down"),
        ):
            self.assertFalse(is_reachable(self.settings))

    def test_chat_refuses_redirect_off_base_url(self) -> None:
        """A 307 must not deliver the prompt to another host."""
        hits: list[bytes] = []

        def _serve(sock: socket.socket, response: bytes, record: list[bytes] | None) -> None:
            sock.settimeout(2)
            try:
                conn, _ = sock.accept()
            except TimeoutError:
                return
            with conn:
                data = b""
                conn.settimeout(1)
                try:
                    while b"\r\n\r\n" not in data:
                        chunk = conn.recv(65536)
                        if not chunk:
                            break
                        data += chunk
                except TimeoutError:
                    pass
                if record is not None:
                    record.append(data)
                conn.sendall(response)

        evil = socket.socket()
        evil.bind(("127.0.0.1", 0))
        evil.listen(1)
        evil_port = evil.getsockname()[1]
        body = b'{"message":{"content":"stolen"}}'
        evil_response = (
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
            + str(len(body)).encode()
            + b"\r\nConnection: close\r\n\r\n"
            + body
        )
        ollama = socket.socket()
        ollama.bind(("127.0.0.1", 0))
        ollama.listen(1)
        ollama_port = ollama.getsockname()[1]
        location = f"http://127.0.0.1:{evil_port}/steal".encode()
        ollama_response = (
            b"HTTP/1.1 307 Temporary Redirect\r\nLocation: "
            + location
            + b"\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
        )
        threads = [
            threading.Thread(target=_serve, args=(evil, evil_response, hits), daemon=True),
            threading.Thread(target=_serve, args=(ollama, ollama_response, None), daemon=True),
        ]
        for thread in threads:
            thread.start()
        settings = OllamaSettings(
            base_url=f"http://127.0.0.1:{ollama_port}",
            fast_model="qwen3.5:9b",
            strong_model="devstral-small-2",
            num_ctx=4096,
        )
        try:
            with self.assertRaises(OllamaError) as raised:
                chat("sys", "write ping", model="fast", settings=settings)
            self.assertIn("redirect", str(raised.exception).lower())
            self.assertEqual(hits, [])
        finally:
            for thread in threads:
                thread.join(timeout=3)
            evil.close()
            ollama.close()

    def test_format_user_task_includes_files(self) -> None:
        text = format_user_task(
            "Add tests",
            files=[{"path": "app.py", "content": "def add(a,b): return a+b"}],
            language="python",
        )
        self.assertIn("Add tests", text)
        self.assertIn("app.py", text)
        self.assertIn("def add", text)


if __name__ == "__main__":
    unittest.main()
