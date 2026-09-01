"""
Tests for harness.iteration (loop detection helpers).
"""

import unittest

from harness.iteration import (
    ROOT_CAUSE_REPEAT_THRESHOLD,
    compute_root_cause_hash,
    increment_iteration,
    iteration_limit_exceeded,
    register_root_cause,
    root_cause_repeated_too_often,
)


def _make_state(current=0, max_=10, last_hash=None, same_count=0):
    return {
        "iteration": {"current": current, "max": max_},
        "loop_detection": {
            "last_root_cause_hash": last_hash,
            "same_root_cause_count": same_count,
        },
    }


class IncrementIterationTestCase(unittest.TestCase):
    def test_increment_iteration_increases_current(self):
        state = _make_state(current=0)
        result = increment_iteration(state)
        self.assertEqual(result, 1)
        self.assertEqual(state["iteration"]["current"], 1)

    def test_increment_iteration_twice_accumulates(self):
        state = _make_state(current=0)
        increment_iteration(state)
        increment_iteration(state)
        self.assertEqual(state["iteration"]["current"], 2)


class IterationLimitExceededTestCase(unittest.TestCase):
    def test_under_max_is_not_exceeded(self):
        state = _make_state(current=5, max_=10)
        self.assertFalse(iteration_limit_exceeded(state))

    def test_at_max_is_not_exceeded(self):
        state = _make_state(current=10, max_=10)
        self.assertFalse(iteration_limit_exceeded(state))

    def test_over_max_is_exceeded(self):
        state = _make_state(current=11, max_=10)
        self.assertTrue(iteration_limit_exceeded(state))


class ComputeRootCauseHashTestCase(unittest.TestCase):
    def test_same_text_same_hash(self):
        self.assertEqual(
            compute_root_cause_hash("Null pointer in auth"),
            compute_root_cause_hash("Null pointer in auth"),
        )

    def test_hash_ignores_case_and_surrounding_whitespace(self):
        self.assertEqual(
            compute_root_cause_hash("Null Pointer In Auth"),
            compute_root_cause_hash("  null pointer in auth  "),
        )

    def test_different_text_different_hash(self):
        self.assertNotEqual(
            compute_root_cause_hash("cause A"),
            compute_root_cause_hash("cause B"),
        )


class RegisterRootCauseTestCase(unittest.TestCase):
    def test_first_registration_sets_count_to_one(self):
        state = _make_state()
        count = register_root_cause(state, "Null pointer in auth")
        self.assertEqual(count, 1)
        self.assertEqual(state["loop_detection"]["same_root_cause_count"], 1)
        self.assertIsNotNone(state["loop_detection"]["last_root_cause_hash"])

    def test_same_cause_again_increments_count(self):
        state = _make_state()
        register_root_cause(state, "Null pointer in auth")
        count = register_root_cause(state, "Null pointer in auth")
        self.assertEqual(count, 2)

    def test_different_cause_resets_count_to_one(self):
        state = _make_state()
        register_root_cause(state, "Null pointer in auth")
        register_root_cause(state, "Null pointer in auth")
        count = register_root_cause(state, "Different bug entirely")
        self.assertEqual(count, 1)


class RootCauseRepeatedTooOftenTestCase(unittest.TestCase):
    def test_below_threshold_is_false(self):
        self.assertFalse(root_cause_repeated_too_often(ROOT_CAUSE_REPEAT_THRESHOLD - 1))

    def test_at_threshold_is_true(self):
        self.assertTrue(root_cause_repeated_too_often(ROOT_CAUSE_REPEAT_THRESHOLD))


if __name__ == "__main__":
    unittest.main()
