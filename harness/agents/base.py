"""
Abstract agent runner interface for the Claude Engineering Harness.

Kept independent of any specific coding agent (Claude Code, or a
future one) so the Harness controller never depends on one particular
implementation — see the "independência de agente" principle in
PROJECT_CONTEXT.md.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


class AgentRunError(Exception):
    """Raised when an agent cannot be invoked at all (e.g. binary missing)."""


@dataclass
class AgentRunOutcome:
    completed: bool
    timed_out: bool
    exit_code: int | None
    stdout: str
    stderr: str


class AgentRunner(ABC):
    @abstractmethod
    def run(self, prompt: str, timeout_seconds: int) -> AgentRunOutcome:
        """
        Invoke the underlying coding agent with `prompt` and wait up to
        `timeout_seconds`. Must never raise for the agent's own failure
        or timeout — report that via AgentRunOutcome instead. Only raise
        AgentRunError when the agent cannot be invoked at all.
        """
