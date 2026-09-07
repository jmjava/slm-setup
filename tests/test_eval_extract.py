"""Tests for MCP output extraction. No Ollama."""

from __future__ import annotations

import unittest

from local_coding_slm.eval.extract import TransportError, extract_files


class ExtractFenceTests(unittest.TestCase):
    def test_language_fence_uses_path_comment(self) -> None:
        text = "```python\n# user_text.py\nprint(1)\n```\n"
        files = extract_files(text)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].path, "user_text.py")
        self.assertEqual(files[0].kind, "fence")
        self.assertIn("print(1)", files[0].content)

    def test_info_string_path(self) -> None:
        text = "```python calc.py\ndef plus():\n    return 1\n```\n"
        files = extract_files(text)
        self.assertEqual(files[0].path, "calc.py")

    def test_multiple_fences(self) -> None:
        text = (
            "```python\n# calc.py\nx = 1\n```\n"
            "```python\n# use.py\ny = 2\n```\n"
        )
        files = extract_files(text)
        self.assertEqual([item.path for item in files], ["calc.py", "use.py"])

    def test_transport_error(self) -> None:
        with self.assertRaises(TransportError):
            extract_files("ERROR: Ollama timed out after 120s")

    def test_empty(self) -> None:
        with self.assertRaises(ValueError):
            extract_files("   ")

    def test_prose_without_fence(self) -> None:
        with self.assertRaises(ValueError):
            extract_files("here is the helper you wanted")

    def test_unified_diff(self) -> None:
        text = (
            "--- a/user_text.py\n"
            "+++ b/user_text.py\n"
            "@@ -1,2 +1,3 @@\n"
            "+def helper():\n"
            " pass\n"
        )
        files = extract_files(text)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].kind, "diff")
        self.assertEqual(files[0].path, "user_text.py")


if __name__ == "__main__":
    unittest.main()
