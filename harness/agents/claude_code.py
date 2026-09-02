"""
Claude Code CLI runner for the Claude Engineering Harness.
"""

import subprocess

from harness.agents.base import AgentRunError, AgentRunOutcome, AgentRunner


class ClaudeCodeRunner(AgentRunner):
    def __init__(self, command: str = "claude") -> None:
        self._command = command

    def run(self, prompt: str, timeout_seconds: int) -> AgentRunOutcome:
        try:
            completed = subprocess.run(
                [
                    self._command,
                    "-p",
                    prompt,
                    "--output-format",
                    "json",
                    "--dangerously-skip-permissions",
                ],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            return AgentRunOutcome(
                completed=False,
                timed_out=True,
                exit_code=None,
                stdout=error.stdout or "",
                stderr=error.stderr or "",
            )
        except FileNotFoundError as error:
            raise AgentRunError(
                f"Claude Code CLI ('{self._command}') not found."
            ) from error

        return AgentRunOutcome(
            completed=True,
            timed_out=False,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
