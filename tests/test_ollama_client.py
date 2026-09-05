import json
import unittest
from io import BytesIO
from unittest.mock import patch
from urllib.error import URLError

from local_coding_slm.ollama_client import (
    OllamaError,
    OllamaSettings,
    chat,
    format_user_task,
    list_model_names,
    status_report,
)


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
            "local_coding_slm.ollama_client.urllib.request.urlopen",
            return_value=_FakeResp(payload),
        ):
            names = list_model_names(self.settings)
        self.assertEqual(names, ["qwen3.5:9b", "devstral-small-2:latest"])

    def test_status_report_marks_present_models(self) -> None:
        payload = {"models": [{"name": "qwen3.5:9b"}]}
        with patch(
            "local_coding_slm.ollama_client.urllib.request.urlopen",
            return_value=_FakeResp(payload),
        ):
            report = status_report(self.settings)
        self.assertIn("host=127.0.0.1", report)
        self.assertIn("fast=qwen3.5:9b present=True", report)
        self.assertIn("strong=devstral-small-2 present=False", report)

    def test_chat_returns_message_content(self) -> None:
        payload = {"message": {"content": "def ping(): return True"}}
        with patch(
            "local_coding_slm.ollama_client.urllib.request.urlopen",
            return_value=_FakeResp(payload),
        ) as mocked:
            text = chat("sys", "write ping", model="fast", settings=self.settings)
        self.assertEqual(text, "def ping(): return True")
        req = mocked.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        self.assertFalse(body["stream"])
        self.assertEqual(body["model"], "qwen3.5:9b")

    def test_unreachable_becomes_ollama_error(self) -> None:
        with patch(
            "local_coding_slm.ollama_client.urllib.request.urlopen",
            side_effect=URLError("down"),
        ):
            with self.assertRaises(OllamaError):
                list_model_names(self.settings)

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
