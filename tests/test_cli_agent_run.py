"""
Tests for the `harness agent-run` CLI command.

Mocks run_current_stage directly — this only tests the CLI wiring
(argument parsing, output formatting, error handling), not the
orchestration logic itself (covered by tests/test_run_current_stage.py)
or ClaudeCodeRunner (covered by tests/test_claude_code_runner.py).
"""

import argparse
import os
import shutil
import tempfile
import unittest
from io import StringIO
from unittest.mock import patch

from harness.cli import command_agent_run
from harness.state import initialize_state


class AgentRunCommandTestCase(unittest.TestCase):
    def setUp(self):
        self._original_cwd = os.getcwd()
        self._temp_dir = tempfile.mkdtemp(prefix="harness-test-")
        os.chdir(self._temp_dir)
        initialize_state()

    def tearDown(self):
        os.chdir(self._original_cwd)
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    @patch("harness.cli.run_current_stage")
    def test_agent_run_prints_result(self, mock_run_current_stage):
        mock_run_current_stage.return_value = {
            "agent": "maestro",
            "from": "TASK",
            "outcome": "SUCCESS",
            "to": "SPECIFICATION",
            "status": "RUNNING",
            "summary": "Captured the task",
        }

        args = argparse.Namespace(timeout=None)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            command_agent_run(args)

        output = mock_stdout.getvalue()
        self.assertIn("SPECIFICATION", output)
        mock_run_current_stage.assert_called_once()

    @patch("harness.cli.run_current_stage")
    def test_agent_run_uses_custom_timeout(self, mock_run_current_stage):
        mock_run_current_stage.return_value = {
            "agent": "maestro",
            "from": "TASK",
            "outcome": "SUCCESS",
            "to": "SPECIFICATION",
            "status": "RUNNING",
            "summary": "x",
        }

        args = argparse.Namespace(timeout=60)

        with patch("sys.stdout", new_callable=StringIO):
            command_agent_run(args)

        _, kwargs = mock_run_current_stage.call_args
        self.assertEqual(kwargs["timeout_seconds"], 60)

    @patch("harness.cli.run_current_stage")
    def test_agent_run_handles_error(self, mock_run_current_stage):
        mock_run_current_stage.side_effect = ValueError(
            "No active workflow stage."
        )

        args = argparse.Namespace(timeout=None)

        with patch("sys.stdout", new_callable=StringIO):
            with self.assertRaises(SystemExit):
                command_agent_run(args)


if __name__ == "__main__":
    unittest.main()
