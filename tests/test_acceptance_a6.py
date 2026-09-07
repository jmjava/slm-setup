"""A6 must execute generated tests. Shape-only `def test` is not a pass."""

from __future__ import annotations

import unittest

from local_coding_slm.eval.acceptance import score_a6
from local_coding_slm.eval.cases import TEST_ADD_GOLDEN, TEST_ADD_SHAPE_ONLY


class A6BehaviorTests(unittest.TestCase):
    def test_golden_executes(self) -> None:
        result = score_a6(TEST_ADD_GOLDEN)
        self.assertTrue(result.passed)
        self.assertEqual(result.layer("behavior").status, "pass")

    def test_shape_only_is_not_a6(self) -> None:
        result = score_a6(TEST_ADD_SHAPE_ONLY)
        self.assertFalse(result.passed)
        self.assertEqual(result.layer("structure").status, "pass")
        self.assertEqual(result.layer("behavior").status, "fail")
        self.assertIn("def test", TEST_ADD_SHAPE_ONLY)


if __name__ == "__main__":
    unittest.main()
