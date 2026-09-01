"""
Tests for harness.roles.
"""

import unittest

from harness.roles import (
    STAGE_ROLE_MAP,
    build_agent_context,
    get_role_for_stage,
    get_role_template_path,
    load_role_prompt,
)


NON_TERMINAL_STAGES = [
    "TASK", "SPECIFICATION", "PLANNING", "EXECUTION",
    "TESTING", "DIAGNOSIS", "FIXING", "REVIEW", "DOCUMENTATION",
]


class RoleMappingTestCase(unittest.TestCase):
    def test_every_non_terminal_stage_has_a_role(self):
        for stage in NON_TERMINAL_STAGES:
            self.assertIn(stage, STAGE_ROLE_MAP)

    def test_get_role_for_stage_returns_expected_role(self):
        self.assertEqual(get_role_for_stage("TESTING"), "TESTER")

    def test_get_role_for_stage_is_case_insensitive(self):
        self.assertEqual(get_role_for_stage("testing"), "TESTER")

    def test_get_role_for_unknown_stage_raises(self):
        with self.assertRaises(ValueError):
            get_role_for_stage("NOT_A_STAGE")

    def test_every_role_template_file_exists_on_disk(self):
        for stage in NON_TERMINAL_STAGES:
            role = get_role_for_stage(stage)
            template_path = get_role_template_path(role)
            self.assertTrue(
                template_path.is_file(),
                f"Missing template for role {role}: {template_path}",
            )

    def test_load_role_prompt_returns_file_content(self):
        content = load_role_prompt("TESTER")
        self.assertIn("TESTER", content.upper())


class BuildAgentContextTestCase(unittest.TestCase):
    def _make_state(self, stage):
        return {
            "workflow": {"current_stage": stage},
            "artifacts": {
                "task": ".harness/task/TASK.md",
                "spec": ".harness/spec/SPEC.md",
                "plan": ".harness/plan/PLAN.md",
                "execution_log": ".harness/execution/EXECUTION_LOG.md",
                "test_results": ".harness/tests/TEST_RESULTS.json",
                "diagnosis": ".harness/diagnosis/DIAGNOSIS.md",
                "review": ".harness/review/REVIEW.md",
                "final_report": ".harness/reports/FINAL_REPORT.md",
            },
            "task": {"id": "T-1", "title": "Sample task"},
            "iteration": {"current": 2, "max": 10},
            "last_result": {"agent": None, "status": None, "summary": None},
        }

    def test_build_agent_context_for_testing_stage(self):
        state = self._make_state("TESTING")
        context = build_agent_context(state)

        self.assertEqual(context["stage"], "TESTING")
        self.assertEqual(context["role"], "TESTER")
        self.assertEqual(context["artifact_path"], ".harness/tests/TEST_RESULTS.json")
        self.assertEqual(context["task_id"], "T-1")
        self.assertEqual(context["iteration"], 2)

    def test_build_agent_context_without_active_stage_raises(self):
        state = self._make_state(None)
        with self.assertRaises(ValueError):
            build_agent_context(state)


if __name__ == "__main__":
    unittest.main()
