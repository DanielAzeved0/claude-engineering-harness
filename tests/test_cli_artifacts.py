"""
Tests for the `harness artifacts` CLI command.
"""

import os
import shutil
import tempfile
import unittest
from io import StringIO
from unittest.mock import patch

from harness.cli import command_artifacts
from harness.state import initialize_state


class ArtifactsCommandTestCase(unittest.TestCase):
    def setUp(self):
        self._original_cwd = os.getcwd()
        self._temp_dir = tempfile.mkdtemp(prefix="harness-test-")
        os.chdir(self._temp_dir)
        initialize_state()

    def tearDown(self):
        os.chdir(self._original_cwd)
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    def test_artifacts_command_lists_all_stages(self):
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            command_artifacts(None)

        output = mock_stdout.getvalue()
        self.assertIn("TASK", output)
        self.assertIn("MAESTRO", output)
        self.assertIn("DOCUMENTATION", output)
        self.assertIn("missing", output)

    def test_artifacts_command_marks_existing_file(self):
        os.makedirs(".harness/spec", exist_ok=True)
        with open(".harness/spec/SPEC.md", "w", encoding="utf-8") as f:
            f.write("content")

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            command_artifacts(None)

        output = mock_stdout.getvalue()
        lines = [line for line in output.splitlines() if "SPECIFICATION" in line]
        self.assertTrue(lines)
        self.assertIn("present", lines[0])

    def test_artifacts_command_works_without_active_task(self):
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            command_artifacts(None)

        output = mock_stdout.getvalue()
        self.assertIn("Artifacts", output)


if __name__ == "__main__":
    unittest.main()
