"""Desktop MCP bring-up and premium review-loop instructions. No GPU."""

from __future__ import annotations

import json
import os
import stat
import unittest
from pathlib import Path
from unittest.mock import patch

from local_coding_slm.envfile import getenv_nonempty
from local_coding_slm.ollama_client import (
    DEFAULT_BASE_URL,
    DEFAULT_FAST_MODEL,
    DEFAULT_NUM_CTX,
    DEFAULT_STRONG_MODEL,
    OllamaSettings,
)
from local_coding_slm.prompts import SYSTEM_PROMPTS
from local_coding_slm.server import local_refactor, local_review

ROOT = Path(__file__).resolve().parents[1]

REVIEW_PHRASES = (
    "accept",
    "rewrite",
    "reject",
    "untrusted",
    "local_review",
    "ERROR:",
    "model=fast",
)

MCP_CURSOR = (
    ROOT / ".cursor" / "mcp.json",
    ROOT / "examples" / "cursor.mcp.json",
)
MCP_CLAUDE = (
    ROOT / ".mcp.json",
    ROOT / "examples" / "claude.mcp.json",
)
MCP_VSCODE = (
    ROOT / ".vscode" / "mcp.json",
    ROOT / "examples" / "vscode.mcp.json",
)
INSTRUCTION_FILES = (
    ROOT / ".cursor" / "rules" / "local-coding-slm.mdc",
    ROOT / "CLAUDE.md",
    ROOT / ".github" / "copilot-instructions.md",
)


def _server_block(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "mcpServers" in data:
        return data["mcpServers"]["local-coding-slm"]
    return data["servers"]["local-coding-slm"]


class GetenvNonemptyTests(unittest.TestCase):
    def test_missing_and_blank_use_default(self) -> None:
        self.assertEqual(getenv_nonempty("MISSING_X", "fallback", {}), "fallback")
        self.assertEqual(getenv_nonempty("BLANK", "fallback", {"BLANK": ""}), "fallback")
        self.assertEqual(getenv_nonempty("SPACES", "fallback", {"SPACES": "  "}), "fallback")
        self.assertEqual(getenv_nonempty("SET", "fallback", {"SET": " http://x "}), "http://x")

    def test_from_env_ignores_empty_interpolations(self) -> None:
        empty = {
            "OLLAMA_BASE_URL": "",
            "OLLAMA_FAST_MODEL": "   ",
            "OLLAMA_STRONG_MODEL": "",
            "OLLAMA_NUM_CTX": "",
        }
        with patch.dict(os.environ, empty, clear=False):
            settings = OllamaSettings.from_env()
        self.assertEqual(settings.base_url, DEFAULT_BASE_URL)
        self.assertEqual(settings.fast_model, DEFAULT_FAST_MODEL)
        self.assertEqual(settings.strong_model, DEFAULT_STRONG_MODEL)
        self.assertEqual(settings.num_ctx, DEFAULT_NUM_CTX)


class McpWrapperTests(unittest.TestCase):
    def test_clients_launch_run_mcp_sh(self) -> None:
        for path in MCP_CURSOR + MCP_CLAUDE + MCP_VSCODE:
            with self.subTest(path=str(path.relative_to(ROOT))):
                block = _server_block(path)
                self.assertIn("run_mcp.sh", block["command"])
                self.assertNotIn("env", block)
                self.assertNotIn("envFile", block)

    def test_wrapper_is_executable(self) -> None:
        wrapper = ROOT / "scripts" / "run_mcp.sh"
        self.assertTrue(wrapper.is_file())
        mode = wrapper.stat().st_mode
        self.assertTrue(mode & stat.S_IXUSR)


class PremiumInstructionTests(unittest.TestCase):
    def test_client_instructions_state_the_apply_gate(self) -> None:
        for path in INSTRUCTION_FILES:
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(path=str(path.relative_to(ROOT))):
                for phrase in REVIEW_PHRASES:
                    self.assertIn(phrase.lower(), text, phrase)

    def test_generation_prompts_prefer_fences(self) -> None:
        for name in ("local_code", "local_refactor", "local_generate_tests"):
            body = SYSTEM_PROMPTS[name]
            self.assertIn("fenced", body)
            self.assertIn("premium agent reviews", body)
        self.assertIn("cannot approve", SYSTEM_PROMPTS["local_review"])
        self.assertIn("accept, rewrite, or reject", SYSTEM_PROMPTS["local_review"])

    def test_tool_docstrings_name_the_reviewer(self) -> None:
        self.assertIn("files=[{path, content}]", local_refactor.__doc__ or "")
        self.assertIn("cannot approve", (local_review.__doc__ or "").lower())
        self.assertIn("accept", (local_review.__doc__ or "").lower())


if __name__ == "__main__":
    unittest.main()
