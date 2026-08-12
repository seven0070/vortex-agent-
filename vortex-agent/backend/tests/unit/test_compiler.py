"""Unit: overlay compiler, no agent."""
import unittest
from evolution.compiler import compile_math, default_overlay, set_overlay


class CompilerUnitTests(unittest.TestCase):
    def tearDown(self):
        set_overlay(None)

    def test_two_operand(self):
        set_overlay(default_overlay())
        self.assertEqual(compile_math("what is 12 times 8"), "print(12 * 8)")

    def test_chained_requires_flag(self):
        set_overlay(default_overlay())
        self.assertNotIn("+ 5", compile_math("what is 15 times 3 plus 5") or "")
        ov = default_overlay()
        ov["compiler"]["chained_arithmetic"] = True
        set_overlay(ov)
        self.assertEqual(compile_math("what is 15 times 3 plus 5"), "print(15 * 3 + 5)")


if __name__ == "__main__":
    unittest.main()
