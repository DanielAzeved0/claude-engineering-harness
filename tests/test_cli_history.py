"""
Tests for the `harness history` CLI command.
"""

import os
import shutil
import tempfile
import unittest
from io import StringIO
from unittest.mock import patch

from harness.cli import _format_history, command_history
from harness.controller import start_task, transition
from harness.state import initialize_state


class FormatHistoryTestCase(unittest.TestCase):
    def test_format_history_includes_transition_and_outcome(self):
        history = [
            {
                "type": "start",
                "from": None,
                "outcome": "START",
                "to": "TASK",
                "timestamp": "2026-09-01T10:00:00+00:00",
            },
            {
                "type": "manual",
                "from": "TASK",
                "outcome": "SUCCESS",
                "to": "SPECIFICATION",
                "timestamp": "2026-09-01T10:00:05+00:00",
            },
        ]

        lines = _format_history(history)

        self.assertEqual(len(lines), 2)
        self.assertIn("TASK -> SPECIFICATION", lines[1])
        self.assertIn("+5.0s", lines[1])

    def test_format_history_empty_list(self):
        self.assertEqual(_format_history([]), [])

    def test_format_history_handles_missing_agent_key(self):
        history = [
            {
                "type": "manual",
                "from": "TASK",
                "outcome": "SUCCESS",
                "to": "SPECIFICATION",
                "timestamp": "2026-09-01T10:00:00+00:00",
            }
        ]

        lines = _format_history(history)

        self.assertIn("agent=-", lines[0])


class HistoryCommandTestCase(unittest.TestCase):
    def setUp(self):
        self._original_cwd = os.getcwd()
        self._temp_dir = tempfile.mkdtemp(prefix="harness-test-")
        os.chdir(self._temp_dir)
        initialize_state()

    def tearDown(self):
        os.chdir(self._original_cwd)
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    def test_history_command_prints_entries(self):
        start_task("T-1", "Sample task")
        transition("SUCCESS")

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            command_history(None)

        output = mock_stdout.getvalue()
        self.assertIn("TASK -> SPECIFICATION", output)

    def test_history_command_with_no_task_shows_placeholder(self):
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            command_history(None)

        output = mock_stdout.getvalue()
        self.assertIn("no history yet", output)

    def test_history_command_includes_summary_from_agent_result(self):
        import json
        from pathlib import Path

        from harness.controller import process_result_file

        start_task("T-2", "Task with agent result")
        transition("SUCCESS")  # TASK -> SPECIFICATION
        transition("SUCCESS")  # SPECIFICATION -> PLANNING
        transition("SUCCESS")  # PLANNING -> EXECUTION

        result_path = Path("tester-result.json")
        result_path.write_text(
            json.dumps(
                {
                    "agent": "tester",
                    "stage": "EXECUTION",
                    "outcome": "SUCCESS",
                    "summary": "All checks passed",
                }
            ),
            encoding="utf-8",
        )
        process_result_file(result_path)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            command_history(None)

        output = mock_stdout.getvalue()
        self.assertIn("All checks passed", output)


if __name__ == "__main__":
    unittest.main()
