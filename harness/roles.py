"""
Agent role definitions for the Claude Engineering Harness.
"""

from pathlib import Path
from typing import Any


ROLES_DIR = Path(__file__).resolve().parent.parent / "roles"


STAGE_ROLE_MAP: dict[str, str] = {
    "TASK": "MAESTRO",
    "SPECIFICATION": "SPEC_ENGINEER",
    "PLANNING": "PLANNER",
    "EXECUTION": "EXECUTOR",
    "TESTING": "TESTER",
    "DIAGNOSIS": "DEBUGGER",
    "FIXING": "EXECUTOR",
    "REVIEW": "REVIEWER",
    "DOCUMENTATION": "DOCUMENTER",
}


ROLE_TEMPLATE_FILENAME: dict[str, str] = {
    "MAESTRO": "maestro.md",
    "SPEC_ENGINEER": "spec-engineer.md",
    "PLANNER": "planner.md",
    "EXECUTOR": "executor.md",
    "TESTER": "tester.md",
    "DEBUGGER": "debugger.md",
    "REVIEWER": "reviewer.md",
    "DOCUMENTER": "documenter.md",
}


STAGE_ARTIFACT_KEY: dict[str, str] = {
    "TASK": "task",
    "SPECIFICATION": "spec",
    "PLANNING": "plan",
    "EXECUTION": "execution_log",
    "TESTING": "test_results",
    "DIAGNOSIS": "diagnosis",
    "FIXING": "execution_log",
    "REVIEW": "review",
    "DOCUMENTATION": "final_report",
}


def get_role_for_stage(stage: str) -> str:
    stage = stage.upper()

    if stage not in STAGE_ROLE_MAP:
        raise ValueError(f"No role defined for stage '{stage}'.")

    return STAGE_ROLE_MAP[stage]


def get_role_template_path(role: str) -> Path:
    role = role.upper()

    if role not in ROLE_TEMPLATE_FILENAME:
        raise ValueError(f"Unknown role '{role}'.")

    return ROLES_DIR / ROLE_TEMPLATE_FILENAME[role]


def load_role_prompt(role: str) -> str:
    template_path = get_role_template_path(role)

    if not template_path.is_file():
        raise FileNotFoundError(f"Role template not found: {template_path}")

    return template_path.read_text(encoding="utf-8")


def build_agent_context(state: dict[str, Any]) -> dict[str, Any]:
    workflow = state["workflow"]
    current_stage = workflow["current_stage"]

    if current_stage is None:
        raise ValueError("No active workflow stage.")

    role = get_role_for_stage(current_stage)
    artifact_key = STAGE_ARTIFACT_KEY[current_stage]

    return {
        "stage": current_stage,
        "role": role,
        "artifact_path": state["artifacts"][artifact_key],
        "task_id": state["task"]["id"],
        "task_title": state["task"]["title"],
        "iteration": state["iteration"]["current"],
        "last_result_summary": state["last_result"]["summary"],
    }
