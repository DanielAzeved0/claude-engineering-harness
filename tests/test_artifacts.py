"""
Tests for harness.artifacts.
"""

import tempfile
import unittest
from pathlib import Path

from harness.artifacts import (
    artifact_exists_for_stage,
    generate_execution_report,
    list_artifact_status,
)


def _make_state(artifact_overrides=None, history=None, escalation=None):
    # Use paths that don't exist by default, ensuring tests can verify non-existent artifacts
    artifacts = {
        "task": ".harness_nonexistent/task/TASK.md",
        "spec": ".harness_nonexistent/spec/SPEC.md",
        "plan": ".harness_nonexistent/plan/PLAN.md",
        "execution_log": ".harness_nonexistent/execution/EXECUTION_LOG.md",
        "test_results": ".harness_nonexistent/tests/TEST_RESULTS.json",
        "diagnosis": ".harness_nonexistent/diagnosis/DIAGNOSIS.md",
        "review": ".harness_nonexistent/review/REVIEW.md",
        "final_report": ".harness_nonexistent/reports/FINAL_REPORT.md",
    }

    if artifact_overrides:
        artifacts.update(artifact_overrides)

    return {
        "task": {
            "id": "T-1",
            "title": "Sample task",
            "created_at": "2026-09-01T10:00:00+00:00",
        },
        "artifacts": artifacts,
        "history": history if history is not None else [],
        "quality_gates": {
            "build": {"required": True, "status": "PENDING"},
        },
        "iteration": {"current": 2, "max": 10},
        "escalation": escalation if escalation is not None else {
            "required": False,
            "reason": None,
        },
    }


class ArtifactExistsForStageTestCase(unittest.TestCase):
    def test_missing_artifact_returns_false(self):
        state = _make_state()
        self.assertFalse(artifact_exists_for_stage(state, "SPECIFICATION"))

    def test_existing_artifact_returns_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "SPEC.md"
            path.write_text("content", encoding="utf-8")
            state = _make_state({"spec": str(path)})
            self.assertTrue(artifact_exists_for_stage(state, "SPECIFICATION"))


class ListArtifactStatusTestCase(unittest.TestCase):
    def test_returns_all_nine_stages_in_workflow_order(self):
        state = _make_state()
        statuses = list_artifact_status(state)

        self.assertEqual(len(statuses), 9)
        self.assertEqual(statuses[0]["stage"], "TASK")
        self.assertEqual(statuses[0]["role"], "MAESTRO")
        self.assertFalse(statuses[0]["exists"])
        self.assertEqual(statuses[-1]["stage"], "DOCUMENTATION")

    def test_marks_existing_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "SPEC.md"
            path.write_text("content", encoding="utf-8")
            state = _make_state({"spec": str(path)})

            statuses = list_artifact_status(state)
            spec_status = next(s for s in statuses if s["stage"] == "SPECIFICATION")
            self.assertTrue(spec_status["exists"])


class GenerateExecutionReportTestCase(unittest.TestCase):
    def test_report_includes_task_and_timeline(self):
        state = _make_state(
            history=[
                {
                    "type": "start",
                    "from": None,
                    "outcome": "START",
                    "to": "TASK",
                    "timestamp": "2026-09-01T10:00:00+00:00",
                }
            ]
        )

        report = generate_execution_report(state)

        self.assertIn("T-1", report)
        self.assertIn("Sample task", report)
        self.assertIn("None -> TASK", report)
        self.assertIn("## Artifacts", report)
        self.assertIn("## Quality Gates", report)
        self.assertIn("## Iterations", report)

    def test_report_lists_artifact_presence(self):
        state = _make_state()

        report = generate_execution_report(state)

        self.assertIn("missing", report)

    def test_report_shows_escalation_reason_when_escalated(self):
        state = _make_state(
            escalation={
                "required": True,
                "reason": "Iteration limit reached (10).",
            }
        )

        report = generate_execution_report(state)

        self.assertIn("Escalated: yes", report)
        self.assertIn("Iteration limit reached (10).", report)

    def test_report_does_not_raise_on_empty_history(self):
        state = _make_state()
        report = generate_execution_report(state)
        self.assertIn("# Execution Report", report)


if __name__ == "__main__":
    unittest.main()
