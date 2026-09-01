"""
Tests for the `harness role` CLI command.
"""

import os
import shutil
import tempfile
import unittest
from io import StringIO
from unittest.mock import patch

from harness.cli import command_role
from harness.controller import start_task
from harness.state import initialize_state


class RoleCommandTestCase(unittest.TestCase):
    def setUp(self):
        self._original_cwd = os.getcwd()
        self._temp_dir = tempfile.mkdtemp(prefix="harness-test-")
        os.chdir(self._temp_dir)
        initialize_state()

    def tearDown(self):
        os.chdir(self._original_cwd)
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    def test_role_command_prints_role_for_current_stage(self):
        start_task("T-1", "Sample task")

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            command_role(None)

        output = mock_stdout.getvalue()
        self.assertIn("Stage: TASK", output)
        self.assertIn("Role: MAESTRO", output)

    def test_role_command_without_active_task_errors(self):
        with self.assertRaises(SystemExit):
            command_role(None)


if __name__ == "__main__":
    unittest.main()
