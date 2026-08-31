"""
End-to-end test proving the workflow can be driven entirely by
structured agent results instead of manual `harness transition` calls.

Runs inside an isolated temporary directory; the developer's real
.harness/ state is never touched.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from harness.controller import process_result_file, start_task
from harness.state import initialize_state, load_state


class AgentDrivenWorkflowTestCase(unittest.TestCase):
    def setUp(self):
        self._original_cwd = os.getcwd()
        self._temp_dir = tempfile.mkdtemp(prefix="harness-e2e-")
        os.chdir(self._temp_dir)

        initialize_state()

    def tearDown(self):
        os.chdir(self._original_cwd)
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    def _submit(self, agent, stage, outcome, summary):
        path = Path(f"{agent}-result.json")
        path.write_text(
            json.dumps(
                {
                    "agent": agent,
                    "stage": stage,
                    "outcome": outcome,
                    "summary": summary,
                }
            ),
            encoding="utf-8",
        )
        return process_result_file(path)

    def test_agent_result_driven_workflow_reaches_diagnosis(self):
        start_task("E2E-1", "End to end agent-driven task")

        stage_sequence = ["TASK"]

        result = self._submit("planner", "TASK", "SUCCESS", "Task captured")
        stage_sequence.append(result["to"])

        result = self._submit(
            "spec-writer", "SPECIFICATION", "SUCCESS", "Spec approved"
        )
        stage_sequence.append(result["to"])

        result = self._submit("planner", "PLANNING", "SUCCESS", "Plan ready")
        stage_sequence.append(result["to"])

        result = self._submit(
            "executor", "EXECUTION", "SUCCESS", "Execution finished"
        )
        stage_sequence.append(result["to"])

        result = self._submit("tester", "TESTING", "FAIL", "2 tests failed")
        stage_sequence.append(result["to"])

        self.assertEqual(
            stage_sequence,
            [
                "TASK",
                "SPECIFICATION",
                "PLANNING",
                "EXECUTION",
                "TESTING",
                "DIAGNOSIS",
            ],
        )

        state = load_state()

        self.assertEqual(state["workflow"]["current_stage"], "DIAGNOSIS")
        self.assertEqual(state["workflow"]["status"], "RUNNING")
        self.assertEqual(state["last_result"]["agent"], "tester")
        self.assertEqual(state["last_result"]["status"], "FAIL")

        # start_task entry + 5 agent-result entries
        self.assertEqual(len(state["history"]), 6)

        agent_result_entries = [
            entry
            for entry in state["history"]
            if entry.get("type") == "agent_result"
        ]
        self.assertEqual(len(agent_result_entries), 5)
        self.assertTrue(
            all("timestamp" in entry for entry in agent_result_entries)
        )


if __name__ == "__main__":
    unittest.main()
