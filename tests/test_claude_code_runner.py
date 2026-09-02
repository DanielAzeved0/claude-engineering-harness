"""
Tests for harness.agents.claude_code.ClaudeCodeRunner.

Every subprocess.run call is mocked — these tests never invoke a real
Claude Code CLI.
"""

import subprocess
import unittest
from unittest.mock import MagicMock, patch

from harness.agents.base import AgentRunError
from harness.agents.claude_code import ClaudeCodeRunner


class ClaudeCodeRunnerTestCase(unittest.TestCase):
    def setUp(self):
        self.runner = ClaudeCodeRunner()

    @patch("harness.agents.claude_code.subprocess.run")
    def test_successful_run_returns_completed_outcome(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="done", stderr="")

        outcome = self.runner.run("do the thing", 30)

        self.assertTrue(outcome.completed)
        self.assertFalse(outcome.timed_out)
        self.assertEqual(outcome.exit_code, 0)
        self.assertEqual(outcome.stdout, "done")

        args, kwargs = mock_run.call_args
        command = args[0]
        self.assertEqual(command[0], "claude")
        self.assertIn("-p", command)
        self.assertIn("do the thing", command)
        self.assertIn("--dangerously-skip-permissions", command)
        self.assertEqual(kwargs["timeout"], 30)

    @patch("harness.agents.claude_code.subprocess.run")
    def test_timeout_returns_timed_out_outcome(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd="claude", timeout=30, output="partial", stderr="err"
        )

        outcome = self.runner.run("do the thing", 30)

        self.assertFalse(outcome.completed)
        self.assertTrue(outcome.timed_out)
        self.assertIsNone(outcome.exit_code)
        self.assertEqual(outcome.stdout, "partial")

    @patch("harness.agents.claude_code.subprocess.run")
    def test_missing_binary_raises_agent_run_error(self, mock_run):
        mock_run.side_effect = FileNotFoundError("no such file")

        with self.assertRaises(AgentRunError):
            self.runner.run("do the thing", 30)

    def test_custom_command_name(self):
        runner = ClaudeCodeRunner(command="my-claude")

        with patch("harness.agents.claude_code.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            runner.run("x", 10)

            args, _ = mock_run.call_args
            self.assertEqual(args[0][0], "my-claude")


if __name__ == "__main__":
    unittest.main()
