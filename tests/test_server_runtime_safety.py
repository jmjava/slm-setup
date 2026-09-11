"""Server start must call classify_base_url. Leftover #9 CI step stays."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from local_coding_slm.safety import CheckResult, classify_base_url
from local_coding_slm.server import enforce_runtime_base_url, main

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "src" / "local_coding_slm" / "server.py"
WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"
CI_COMMAND = "python scripts/check_deployment_safety.py --skip-listen"


class ServerRuntimeSafetyTests(unittest.TestCase):
    def test_server_start_calls_classify_base_url(self) -> None:
        passed = CheckResult("base_url", "pass", "OLLAMA_BASE_URL is loopback")
        with (
            patch("local_coding_slm.server.mcp.run") as run,
            patch(
                "local_coding_slm.server.classify_base_url",
                return_value=passed,
            ) as classify,
            patch.dict(
                os.environ,
                {"OLLAMA_BASE_URL": "http://127.0.0.1:11434"},
                clear=False,
            ),
        ):
            main()
        classify.assert_called()
        self.assertEqual(classify.call_args.args[0], "http://127.0.0.1:11434")
        run.assert_called_once_with(transport="stdio")

    def test_server_start_refuses_fail_base_url(self) -> None:
        self.assertEqual(classify_base_url("http://8.8.8.8:11434").status, "fail")
        with (
            patch("local_coding_slm.server.mcp.run") as run,
            patch.dict(
                os.environ,
                {"OLLAMA_BASE_URL": "http://8.8.8.8:11434"},
                clear=False,
            ),
        ):
            with self.assertRaises(SystemExit) as raised:
                main()
        self.assertEqual(raised.exception.code, 1)
        run.assert_not_called()

    def test_server_start_allows_loopback(self) -> None:
        with (
            patch("local_coding_slm.server.mcp.run") as run,
            patch.dict(
                os.environ,
                {"OLLAMA_BASE_URL": "http://127.0.0.1:11434"},
                clear=False,
            ),
        ):
            main()
        run.assert_called_once_with(transport="stdio")

    def test_server_start_hostname_fails(self) -> None:
        # Leftover #11: hostname URLs fail; leftover #10 still refuse on fail.
        url = "https://my-ollama.evil.com"
        self.assertEqual(classify_base_url(url).status, "fail")
        with (
            patch("local_coding_slm.server.mcp.run") as run,
            patch.dict(os.environ, {"OLLAMA_BASE_URL": url}, clear=False),
        ):
            with self.assertRaises(SystemExit) as raised:
                main()
        self.assertEqual(raised.exception.code, 1)
        run.assert_not_called()

    def test_server_imports_classify_base_url(self) -> None:
        text = SERVER.read_text(encoding="utf-8")
        self.assertIn("from local_coding_slm.safety import classify_base_url", text)
        self.assertIn("classify_base_url", text)

    def test_leftover_9_ci_deployment_safety_step_stays(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("- name: Deployment safety", text)
        self.assertIn(CI_COMMAND, text)

    def test_enforce_runtime_base_url_uses_default_when_unset(self) -> None:
        env = {key: value for key, value in os.environ.items() if key != "OLLAMA_BASE_URL"}
        with (
            patch.dict(os.environ, env, clear=True),
            patch(
                "local_coding_slm.server.classify_base_url",
                return_value=CheckResult("base_url", "pass", "loopback"),
            ) as classify,
        ):
            enforce_runtime_base_url()
        classify.assert_called_once()
        self.assertIn("127.0.0.1", classify.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
