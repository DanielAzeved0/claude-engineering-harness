"""
Deterministic workflow controller for the Claude Engineering Harness.
"""

import json
from pathlib import Path
from typing import Any

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
from harness.state import load_state, now_iso, save_state
from harness.transitions import TERMINAL_STAGES, get_next_stage


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
