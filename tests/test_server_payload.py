"""MCP server refuses unsafe payloads before calling Ollama."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from local_coding_slm.server import _run_tool


class ServerPayloadTests(unittest.TestCase):
    @patch("local_coding_slm.server.chat")
    def test_env_file_never_calls_ollama(self, chat: object) -> None:
        text = _run_tool(
            "local_code",
            "rename a helper",
            [{"path": ".env", "content": "OLLAMA_BASE_URL=http://127.0.0.1:11434"}],
            None,
            None,
            "fast",
            None,
        )
        self.assertIn("secrets_file", text)
        self.assertTrue(text.startswith("ERROR:"))
        chat.assert_not_called()  # type: ignore[attr-defined]

    @patch("local_coding_slm.server.chat")
    def test_private_key_never_calls_ollama(self, chat: object) -> None:
        text = _run_tool(
            "local_refactor",
            "extract a helper",
            [{"path": "key.py", "content": "-----BEGIN RSA PRIVATE KEY-----\nxx\n"}],
            None,
            None,
            "fast",
            700,
        )
        self.assertIn("secret_content", text)
        chat.assert_not_called()  # type: ignore[attr-defined]

    @patch("local_coding_slm.server.chat", return_value="ok")
    def test_clean_payload_reaches_chat(self, chat: object) -> None:
        text = _run_tool(
            "local_code",
            "write clamp",
            [{"path": "spec.md", "content": "clamp value between lo and hi"}],
            "python",
            None,
            "fast",
            400,
        )
        self.assertEqual(text, "ok")
        chat.assert_called_once()  # type: ignore[attr-defined]


if __name__ == "__main__":
    unittest.main()
