"""
Tests for the agent result processor (harness.controller.process_result_file).

Each test runs inside an isolated temporary directory so the developer's
real .harness/ state is never touched.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from harness.controller import process_result_file, start_task, transition
from harness.state import initialize_state, load_state


class ResultProcessingTestCase(unittest.TestCase):
    def setUp(self):
        self._original_cwd = os.getcwd()
        self._temp_dir = tempfile.mkdtemp(prefix="harness-test-")
        os.chdir(self._temp_dir)

        initialize_state()

    def tearDown(self):
        os.chdir(self._original_cwd)
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    def _advance_to_testing(self):
        start_task("T-1", "Sample task")
        transition("SUCCESS")  # TASK -> SPECIFICATION
        transition("SUCCESS")  # SPECIFICATION -> PLANNING
        transition("SUCCESS")  # PLANNING -> EXECUTION
        transition("SUCCESS")  # EXECUTION -> TESTING

    def _write_result(self, filename, data):
        path = Path(filename)
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_valid_agent_result_advances_workflow(self):
        self._advance_to_testing()

        result_path = self._write_result(
            "tester-result.json",
            {
                "agent": "tester",
                "stage": "TESTING",
                "outcome": "FAIL",
                "summary": "Simulated test failure",
                "artifacts": [],
                "metadata": {"failed_tests": 1},
            },
        )

        result = process_result_file(result_path)

        self.assertEqual(result["to"], "DIAGNOSIS")
        self.assertEqual(result["status"], "RUNNING")

        state = load_state()

        self.assertEqual(state["workflow"]["current_stage"], "DIAGNOSIS")
        self.assertEqual(state["workflow"]["status"], "RUNNING")
        self.assertEqual(state["last_result"]["agent"], "tester")
        self.assertEqual(state["last_result"]["status"], "FAIL")

        history_entry = state["history"][-1]
        self.assertEqual(history_entry["agent"], "tester")
        self.assertEqual(history_entry["from"], "TESTING")
        self.assertEqual(history_entry["to"], "DIAGNOSIS")
        self.assertEqual(history_entry["outcome"], "FAIL")

    def test_stage_mismatch_is_rejected(self):
        self._advance_to_testing()

        result_path = self._write_result(
            "executor-result.json",
            {
                "agent": "executor",
                "stage": "EXECUTION",
                "outcome": "SUCCESS",
                "summary": "Execution finished",
            },
        )

        with self.assertRaises(ValueError):
            process_result_file(result_path)

        # A rejected result must not move the workflow forward.
        state = load_state()
        self.assertEqual(state["workflow"]["current_stage"], "TESTING")

    def test_invalid_json_is_rejected(self):
        result_path = Path("broken-result.json")
        result_path.write_text("{not valid json", encoding="utf-8")

        with self.assertRaises(ValueError):
            process_result_file(result_path)

    def test_missing_required_field_is_rejected(self):
        self._advance_to_testing()

        result_path = self._write_result(
            "incomplete-result.json",
            {
                "agent": "tester",
                "stage": "TESTING",
                "outcome": "FAIL",
            },
        )

        with self.assertRaises(ValueError):
            process_result_file(result_path)

    def test_empty_required_field_is_rejected(self):
        self._advance_to_testing()

        result_path = self._write_result(
            "empty-summary-result.json",
            {
                "agent": "tester",
                "stage": "TESTING",
                "outcome": "FAIL",
                "summary": "   ",
            },
        )

        with self.assertRaises(ValueError):
            process_result_file(result_path)

    def test_missing_result_file_is_rejected(self):
        with self.assertRaises(FileNotFoundError):
            process_result_file("does-not-exist.json")

    def test_invalid_outcome_for_stage_is_rejected(self):
        self._advance_to_testing()

        result_path = self._write_result(
            "bad-outcome-result.json",
            {
                "agent": "tester",
                "stage": "TESTING",
                "outcome": "SUCCESS",
                "summary": "Wrong outcome for this stage",
            },
        )

        with self.assertRaises(ValueError):
            process_result_file(result_path)

    def test_no_active_workflow_is_rejected(self):
        result_path = self._write_result(
            "orphan-result.json",
            {
                "agent": "tester",
                "stage": "TASK",
                "outcome": "SUCCESS",
                "summary": "No workflow started",
            },
        )

        with self.assertRaises(ValueError):
            process_result_file(result_path)

    def test_terminal_stage_is_rejected(self):
        start_task("T-2", "Task that gets blocked")
        transition("FAIL")  # TASK -> BLOCKED (terminal)

        result_path = self._write_result(
            "late-result.json",
            {
                "agent": "tester",
                "stage": "BLOCKED",
                "outcome": "SUCCESS",
                "summary": "Should not be accepted",
            },
        )

        with self.assertRaises(ValueError):
            process_result_file(result_path)


if __name__ == "__main__":
    unittest.main()
