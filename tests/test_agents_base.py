"""
Tests for harness.agents.base.
"""

import unittest

from harness.agents.base import AgentRunError, AgentRunOutcome, AgentRunner


class FakeRunner(AgentRunner):
    def run(self, prompt: str, timeout_seconds: int) -> AgentRunOutcome:
        return AgentRunOutcome(
            completed=True,
            timed_out=False,
            exit_code=0,
            stdout=f"ran: {prompt}",
            stderr="",
        )


class AgentRunnerTestCase(unittest.TestCase):
    def test_cannot_instantiate_abstract_base_directly(self):
        with self.assertRaises(TypeError):
            AgentRunner()

    def test_concrete_subclass_can_run(self):
        runner = FakeRunner()
        outcome = runner.run("hello", 30)

        self.assertTrue(outcome.completed)
        self.assertFalse(outcome.timed_out)
        self.assertEqual(outcome.exit_code, 0)
        self.assertIn("hello", outcome.stdout)


class AgentRunOutcomeTestCase(unittest.TestCase):
    def test_holds_all_fields(self):
        outcome = AgentRunOutcome(
            completed=False,
            timed_out=True,
            exit_code=None,
            stdout="partial output",
            stderr="",
        )

        self.assertFalse(outcome.completed)
        self.assertTrue(outcome.timed_out)
        self.assertIsNone(outcome.exit_code)
        self.assertEqual(outcome.stdout, "partial output")


class AgentRunErrorTestCase(unittest.TestCase):
    def test_is_an_exception(self):
        self.assertTrue(issubclass(AgentRunError, Exception))


if __name__ == "__main__":
    unittest.main()
