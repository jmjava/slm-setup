"""Payload guards. No Ollama."""

from __future__ import annotations

import unittest

from local_coding_slm.eval.routing import mechanical_signals, route
from local_coding_slm.payload import MAX_FILES, inspect_payload, refusal_message


class InspectPayloadTests(unittest.TestCase):
    def test_clean_snippet_ok(self) -> None:
        self.assertIsNone(
            inspect_payload([{"path": "add.py", "content": "def add(a, b): return a + b\n"}])
        )

    def test_env_file(self) -> None:
        self.assertEqual(
            inspect_payload([{"path": ".env", "content": "K=v"}]),
            "secrets_file",
        )

    def test_env_example_ok(self) -> None:
        self.assertIsNone(
            inspect_payload([{"path": ".env.example", "content": "OLLAMA_BASE_URL="}])
        )

    def test_private_key_content(self) -> None:
        self.assertEqual(
            inspect_payload(
                [
                    {
                        "path": "app.py",
                        "content": "-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n",
                    }
                ]
            ),
            "secret_content",
        )

    def test_password_in_code_is_not_a_secret_blob(self) -> None:
        self.assertIsNone(
            inspect_payload(
                [{"path": "auth.py", "content": "def login(user, password):\n    return user.name\n"}]
            )
        )

    def test_too_many_files(self) -> None:
        files = [{"path": f"f{i}.py", "content": "x"} for i in range(MAX_FILES + 1)]
        self.assertEqual(inspect_payload(files), "too_many_files")

    def test_max_tokens(self) -> None:
        self.assertEqual(inspect_payload([], max_tokens=9000), "max_tokens_too_large")

    def test_route_uses_payload_guard(self) -> None:
        decision = route(
            mechanical_signals(),
            files=[{"path": "id_rsa", "content": "not-a-real-key"}],
        )
        self.assertEqual(decision.action, "keep")
        self.assertEqual(decision.reason, "secrets_file")

    def test_refusal_message_is_transport_shaped(self) -> None:
        self.assertTrue(refusal_message("secrets_file").startswith("ERROR:"))


if __name__ == "__main__":
    unittest.main()
