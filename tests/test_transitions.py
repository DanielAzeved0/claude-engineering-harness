"""
Tests for the workflow transition engine.
"""

import unittest

from harness.transitions import get_allowed_outcomes, get_next_stage


class TransitionsTestCase(unittest.TestCase):
    def test_valid_transition(self):
        self.assertEqual(get_next_stage("TASK", "SUCCESS"), "SPECIFICATION")

    def test_invalid_outcome_is_rejected(self):
        with self.assertRaises(ValueError):
            get_next_stage("TASK", "PASS")

    def test_unknown_stage_is_rejected(self):
        with self.assertRaises(ValueError):
            get_next_stage("NOT_A_STAGE", "SUCCESS")

    def test_terminal_stage_cannot_transition(self):
        with self.assertRaises(ValueError):
            get_next_stage("COMPLETE", "SUCCESS")

    def test_get_allowed_outcomes(self):
        self.assertEqual(
            set(get_allowed_outcomes("TESTING")),
            {"PASS", "FAIL"},
        )


if __name__ == "__main__":
    unittest.main()
