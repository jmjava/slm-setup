"""Unit tests for merge_dotenv function."""

from __future__ import annotations

import unittest
from collections.abc import MutableMapping

from local_coding_slm.envfile import merge_dotenv


class TestMergeDotenv(unittest.TestCase):
    """Tests for the merge_dotenv function."""

    def setUp(self) -> None:
        self.environ: MutableMapping[str, str] = {}

    def test_comment_lines_ignored(self) -> None:
        merge_dotenv(["# This is a comment", "FOO=bar"], self.environ)
        self.assertEqual(self.environ["FOO"], "bar")

    def test_blank_lines_ignored(self) -> None:
        merge_dotenv(["", "   ", "BAR=baz"], self.environ)
        self.assertEqual(self.environ["BAR"], "baz")

    def test_quoted_values_unquoted(self) -> None:
        merge_dotenv(['KEY="quoted value"', "SINGLE='has spaces'"], self.environ)
        self.assertEqual(self.environ["KEY"], "quoted value")
        self.assertEqual(self.environ["SINGLE"], "has spaces")

    def test_missing_key_is_set(self) -> None:
        merge_dotenv(["NEW_KEY=new_value"], self.environ)
        self.assertEqual(self.environ["NEW_KEY"], "new_value")

    def test_empty_existing_env_value_replaced(self) -> None:
        self.environ["EMPTY"] = ""
        merge_dotenv(["EMPTY=replaced"], self.environ)
        self.assertEqual(self.environ["EMPTY"], "replaced")

    def test_non_empty_existing_env_value_kept(self) -> None:
        self.environ["EXISTING"] = "original"
        merge_dotenv(["EXISTING=from_env"], self.environ)
        self.assertEqual(self.environ["EXISTING"], "original")

    def test_key_without_value_ignored(self) -> None:
        merge_dotenv(["NOEQUALSSIGN"], self.environ)
        self.assertNotIn("NOEQUALSSIGN", self.environ)

    def test_empty_key_ignored(self) -> None:
        merge_dotenv([" =value"], self.environ)
        self.assertNotIn("", self.environ)


if __name__ == "__main__":
    unittest.main()
