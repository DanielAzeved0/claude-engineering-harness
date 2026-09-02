"""
Deterministic workflow controller for the Claude Engineering Harness.
"""

import json
from pathlib import Path
from typing import Any

from harness.agents.base import AgentRunner
from harness.artifacts import (
    EXECUTION_REPORT_PATH,
    artifact_exists_for_stage,
    generate_execution_report,
)
from harness.iteration import (
    increment_iteration,
    iteration_limit_exceeded,
    register_root_cause,
    root_cause_repeated_too_often,
)
from harness.models import parse_agent_result
from harness.roles import build_agent_context, load_role_prompt
from harness.state import load_state, now_iso, save_state
from harness.transitions import TERMINAL_STAGES, get_allowed_outcomes, get_next_stage


def _apply_stage_transition(state: dict, outcome: str) -> tuple:
    """
    Compute and apply the next stage for the given state, using the
    transition engine in transitions.py as the single source of truth.
    Mutates `state` only after the transition has been validated, so a
    rejected outcome never leaves partial state behind.

    If the computed next stage is DIAGNOSIS and the iteration limit has
    been reached, the workflow is escalated instead of entering another
    diagnosis cycle.
    """

    workflow = state["workflow"]
    current_stage = workflow["current_stage"]

    if current_stage is None:
        raise ValueError(
            "No active workflow stage. Start a task before transitioning."
        )

    next_stage = get_next_stage(
        current_stage=current_stage,
        outcome=outcome,
    )

    if next_stage == "DIAGNOSIS":
        increment_iteration(state)

        if iteration_limit_exceeded(state):
            next_stage = "ESCALATED"
            state["escalation"] = {
                "required": True,
                "reason": (
                    f"Iteration limit reached ({state['iteration']['max']})."
                ),
            }

    workflow["previous_stage"] = current_stage
    workflow["current_stage"] = next_stage
    workflow["status"] = next_stage if next_stage in TERMINAL_STAGES else "RUNNING"

    return current_stage, next_stage


def _write_execution_report_if_complete(state: dict) -> None:
    if state["workflow"]["current_stage"] != "COMPLETE":
        return

    try:
        EXECUTION_REPORT_PATH.write_text(
            generate_execution_report(state), encoding="utf-8"
        )
    except (OSError, KeyError) as error:
        print(f"Warning: could not write execution report: {error}")


def transition(outcome: str) -> dict[str, Any]:
    """
    Apply a valid workflow transition triggered manually via the CLI.
    """

    state = load_state()
    workflow = state["workflow"]

    outcome = outcome.upper()

    previous_stage, next_stage = _apply_stage_transition(state, outcome)

    state["history"].append(
        {
            "type": "manual",
            "from": previous_stage,
            "outcome": outcome,
            "to": next_stage,
            "timestamp": now_iso(),
        }
    )

    save_state(state)

    _write_execution_report_if_complete(state)

    return {
        "from": previous_stage,
        "outcome": outcome,
        "to": next_stage,
        "status": workflow["status"],
    }


def process_result_file(path) -> dict[str, Any]:
    """
    Read a structured agent result file, validate it against the current
    workflow stage, and automatically apply the corresponding transition.

    Nothing is persisted unless every validation step succeeds.
    """

    result_path = Path(path)

    if not result_path.is_file():
        raise FileNotFoundError(f"Result file not found: {result_path}")

    try:
        with result_path.open("r", encoding="utf-8") as file:
            raw_data = json.load(file)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Result file '{result_path}' contains invalid JSON: {error}"
        ) from error

    agent_result = parse_agent_result(raw_data)

    state = load_state()
    workflow = state["workflow"]
    current_stage = workflow["current_stage"]

    if current_stage is None:
        raise ValueError(
            "No active workflow stage. Start a task before processing results."
        )

    if agent_result.stage != current_stage:
        raise ValueError(
            f"Result stage '{agent_result.stage}' does not match "
            f"current workflow stage '{current_stage}'."
        )

    previous_stage, next_stage = _apply_stage_transition(
        state, agent_result.outcome
    )

    if agent_result.stage == "DIAGNOSIS" and next_stage == "FIXING":
        root_cause = str(agent_result.metadata.get("root_cause") or agent_result.summary)
        repeat_count = register_root_cause(state, root_cause)

        if root_cause_repeated_too_often(repeat_count):
            next_stage = "ESCALATED"
            workflow["current_stage"] = "ESCALATED"
            workflow["status"] = "ESCALATED"
            state["escalation"] = {
                "required": True,
                "reason": (
                    f"Root cause repeated {repeat_count} times without resolution."
                ),
            }

    state["last_result"] = {
        "agent": agent_result.agent,
        "status": agent_result.outcome,
        "summary": agent_result.summary,
    }

    state["history"].append(
        {
            "type": "agent_result",
            "agent": agent_result.agent,
            "from": previous_stage,
            "outcome": agent_result.outcome,
            "to": next_stage,
            "summary": agent_result.summary,
            "artifact_present": artifact_exists_for_stage(state, agent_result.stage),
            "artifacts": agent_result.artifacts,
            "metadata": agent_result.metadata,
            "result_file": str(result_path),
            "timestamp": now_iso(),
        }
    )

    save_state(state)

    _write_execution_report_if_complete(state)

    return {
        "agent": agent_result.agent,
        "from": previous_stage,
        "outcome": agent_result.outcome,
        "to": next_stage,
        "status": workflow["status"],
        "summary": agent_result.summary,
    }


def start_task(task_id: str, title: str) -> dict[str, Any]:
    """
    Start a new Harness task.
    """

    state = load_state()

    workflow = state["workflow"]

    if workflow["status"] not in {
        "IDLE",
        "COMPLETE",
        "FAILED",
        "BLOCKED",
        "ESCALATED",
    }:
        raise ValueError(
            "A workflow is already active. "
            "Complete or reset it before starting a new task."
        )

    timestamp = now_iso()

    state["task"] = {
        "id": task_id,
        "title": title,
        "created_at": timestamp,
    }

    workflow["status"] = "RUNNING"
    workflow["current_stage"] = "TASK"
    workflow["previous_stage"] = None
    workflow["started_at"] = timestamp

    state["iteration"]["current"] = 0

    state["loop_detection"] = {
        "same_root_cause_count": 0,
        "last_root_cause_hash": None,
    }

    state["escalation"] = {
        "required": False,
        "reason": None,
    }

    state["history"] = [
        {
            "type": "start",
            "from": None,
            "outcome": "START",
            "to": "TASK",
            "timestamp": timestamp,
        }
    ]

    save_state(state)

    return state


DEFAULT_AGENT_TIMEOUT_SECONDS = 1800


def build_agent_prompt(context: dict, role_prompt: str, result_path: Path) -> str:
    allowed_outcomes = get_allowed_outcomes(context["stage"])

    return (
        "## Harness Override\n\n"
        "This section overrides anything below it, including the role "
        "description. You do not control, execute, or trigger workflow "
        "transitions. You never run `harness transition`, `harness "
        "result`, `harness agent-run`, or any other Harness command. You "
        "only report your outcome by writing the JSON file described in "
        "'Harness Result Protocol' below — the Harness process applies "
        "the transition after you exit.\n\n"
        f"{role_prompt}\n\n"
        "## Harness Context\n\n"
        f"- Task ID: {context['task_id']}\n"
        f"- Task Title: {context['task_title']}\n"
        f"- Stage: {context['stage']}\n"
        f"- Expected artifact: {context['artifact_path']}\n"
        f"- Iteration: {context['iteration']}\n"
        f"- Last result summary: {context['last_result_summary']}\n\n"
        "## Harness Result Protocol\n\n"
        "When you finish this role's work, write a JSON file to exactly "
        f"this path: {result_path}\n\n"
        "The JSON must have this shape:\n\n"
        "{\n"
        '  "agent": "<your role, lowercase>",\n'
        f'  "stage": "{context["stage"]}",\n'
        f'  "outcome": "<one of: {", ".join(allowed_outcomes)}>",\n'
        '  "summary": "<one-line summary of what happened>",\n'
        '  "artifacts": ["<paths of files you created or modified>"],\n'
        '  "metadata": {}\n'
        "}\n\n"
        "You report the outcome. You do NOT choose or execute the next "
        "workflow stage — the Harness applies the transition "
        "deterministically based on what you report. Do not run any "
        "Harness command yourself."
    )


def run_current_stage(
    runner: AgentRunner, timeout_seconds: int = DEFAULT_AGENT_TIMEOUT_SECONDS
) -> dict[str, Any]:
    state = load_state()
    context = build_agent_context(state)
    role_prompt = load_role_prompt(context["role"])

    result_path = Path(
        f".harness/results/{context['stage'].lower()}-"
        f"{now_iso().replace(':', '-')}.json"
    )

    prompt = build_agent_prompt(context, role_prompt, result_path)

    outcome = runner.run(prompt, timeout_seconds)

    def _write_fallback(reason: str) -> None:
        fallback = {
            "agent": context["role"].lower(),
            "stage": context["stage"],
            "outcome": "FAIL",
            "summary": f"Agent {reason}.",
            "metadata": {
                "stdout_tail": outcome.stdout[-500:],
                "stderr_tail": outcome.stderr[-500:],
            },
        }
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(fallback), encoding="utf-8")

    if not result_path.is_file():
        if outcome.timed_out:
            reason = f"timed out after {timeout_seconds}s"
        else:
            reason = (
                "exited without producing a result file "
                f"(exit_code={outcome.exit_code})"
            )
        _write_fallback(reason)

    try:
        return process_result_file(result_path)
    except ValueError:
        _write_fallback("wrote an unusable result file")
        return process_result_file(result_path)
