"""
Tests for harness.controller.build_agent_prompt and run_current_stage.

Uses fake AgentRunner implementations (test doubles) — no subprocess,
no real Claude Code invocation.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from harness.agents.base import AgentRunner, AgentRunOutcome
from harness.controller import build_agent_prompt, run_current_stage, start_task
from harness.state import initialize_state, load_state


class ResultWritingRunner(AgentRunner):
    """Fake runner that writes a valid result file, simulating a real agent."""

    def __init__(self, outcome_json):
        self._outcome_json = outcome_json

    def run(self, prompt, timeout_seconds):
        result_path = self._extract_result_path(prompt)
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(self._outcome_json), encoding="utf-8")
        return AgentRunOutcome(
            completed=True, timed_out=False, exit_code=0, stdout="", stderr=""
        )

    @staticmethod
    def _extract_result_path(prompt):
        for line in prompt.splitlines():
            if "this path:" in line:
                return Path(line.split("this path:", 1)[1].strip())
        raise AssertionError("prompt did not include a result path")


class TimeoutRunner(AgentRunner):
    def run(self, prompt, timeout_seconds):
        return AgentRunOutcome(
            completed=False, timed_out=True, exit_code=None, stdout="", stderr=""
        )


class SilentRunner(AgentRunner):
    """Simulates an agent that exits without ever writing a result file."""

    def run(self, prompt, timeout_seconds):
        return AgentRunOutcome(
            completed=True, timed_out=False, exit_code=0, stdout="no-op", stderr=""
        )


class TruncatedResultRunner(AgentRunner):
    """Simulates an agent killed mid-write, leaving an unusable result file."""

    def run(self, prompt, timeout_seconds):
        result_path = ResultWritingRunner._extract_result_path(prompt)
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text('{"agent": "tester", "stage": "TASK"', encoding="utf-8")
        return AgentRunOutcome(
            completed=False, timed_out=True, exit_code=None, stdout="", stderr=""
        )


class RecordingRunner(AgentRunner):
    def __init__(self):
        self.received_timeout = None

    def run(self, prompt, timeout_seconds):
        self.received_timeout = timeout_seconds
        result_path = ResultWritingRunner._extract_result_path(prompt)
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(
            json.dumps(
                {
                    "agent": "maestro",
                    "stage": "TASK",
                    "outcome": "SUCCESS",
                    "summary": "ok",
                }
            ),
            encoding="utf-8",
        )
        return AgentRunOutcome(
            completed=True, timed_out=False, exit_code=0, stdout="", stderr=""
        )


class BuildAgentPromptTestCase(unittest.TestCase):
    def test_prompt_includes_role_template_context_and_protocol(self):
        context = {
            "stage": "TESTING",
            "role": "TESTER",
            "artifact_path": ".harness/tests/TEST_RESULTS.json",
            "task_id": "T-1",
            "task_title": "Sample task",
            "iteration": 0,
            "last_result_summary": None,
        }
        result_path = Path(".harness/results/testing-2026-01-01.json")

        prompt = build_agent_prompt(context, "ROLE TEMPLATE TEXT", result_path)

        self.assertIn("ROLE TEMPLATE TEXT", prompt)
        self.assertIn("T-1", prompt)
        self.assertIn(str(result_path), prompt)
        self.assertIn("PASS", prompt)
        self.assertIn("FAIL", prompt)


class RunCurrentStageTestCase(unittest.TestCase):
    def setUp(self):
        self._original_cwd = os.getcwd()
        self._temp_dir = tempfile.mkdtemp(prefix="harness-test-")
        os.chdir(self._temp_dir)
        initialize_state()
        start_task("T-1", "Sample task")

    def tearDown(self):
        os.chdir(self._original_cwd)
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    def test_successful_agent_run_advances_workflow(self):
        runner = ResultWritingRunner(
            {
                "agent": "maestro",
                "stage": "TASK",
                "outcome": "SUCCESS",
                "summary": "Captured the task",
            }
        )

        result = run_current_stage(runner)

        self.assertEqual(result["to"], "SPECIFICATION")

        state = load_state()
        self.assertEqual(state["workflow"]["current_stage"], "SPECIFICATION")

    def test_timeout_synthesizes_fail_result(self):
        result = run_current_stage(TimeoutRunner(), timeout_seconds=5)

        self.assertEqual(result["outcome"], "FAIL")
        self.assertIn("timed out", result["summary"])

    def test_silent_agent_synthesizes_fail_result(self):
        result = run_current_stage(SilentRunner())

        self.assertEqual(result["outcome"], "FAIL")
        self.assertIn("exited without producing", result["summary"])

    def test_truncated_result_file_synthesizes_fail_result(self):
        result = run_current_stage(TruncatedResultRunner(), timeout_seconds=5)

        self.assertEqual(result["outcome"], "FAIL")
        self.assertIn("unusable", result["summary"])

    def test_timeout_seconds_propagated_to_runner(self):
        runner = RecordingRunner()
        run_current_stage(runner, timeout_seconds=42)

        self.assertEqual(runner.received_timeout, 42)


if __name__ == "__main__":
    unittest.main()
