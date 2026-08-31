"""
Persistent state management for the Claude Engineering Harness.
"""

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HARNESS_DIR = Path(".harness")
STATE_FILE = HARNESS_DIR / "state.json"


DEFAULT_STATE: dict[str, Any] = {
    "harness_version": "0.1.0",
    "workflow": {
        "status": "IDLE",
        "current_stage": None,
        "previous_stage": None,
        "started_at": None,
        "updated_at": None,
    },
    "task": {
        "id": None,
        "title": None,
        "created_at": None,
    },
    "iteration": {
        "current": 0,
        "max": 10,
    },
    "loop_detection": {
        "same_root_cause_count": 0,
        "last_root_cause_hash": None,
    },
    "quality_gates": {
        "build": {
            "required": True,
            "status": "PENDING",
        },
        "lint": {
            "required": True,
            "status": "PENDING",
        },
        "unit_tests": {
            "required": True,
            "status": "PENDING",
        },
        "integration_tests": {
            "required": False,
            "status": "PENDING",
        },
        "acceptance_tests": {
            "required": True,
            "status": "PENDING",
        },
        "review": {
            "required": True,
            "status": "PENDING",
        },
    },
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
    "last_result": {
        "agent": None,
        "status": None,
        "summary": None,
    },
    "escalation": {
        "required": False,
        "reason": None,
    },
    "history": [],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_harness_structure() -> None:
    directories = [
        HARNESS_DIR,
        HARNESS_DIR / "task",
        HARNESS_DIR / "spec",
        HARNESS_DIR / "plan",
        HARNESS_DIR / "execution",
        HARNESS_DIR / "tests",
        HARNESS_DIR / "diagnosis",
        HARNESS_DIR / "review",
        HARNESS_DIR / "documentation",
        HARNESS_DIR / "results",
        HARNESS_DIR / "iterations",
        HARNESS_DIR / "reports",
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def initialize_state() -> dict[str, Any]:
    ensure_harness_structure()

    if STATE_FILE.exists():
        raise FileExistsError(
            f"Harness is already initialized: {STATE_FILE}"
        )

    state = deepcopy(DEFAULT_STATE)
    state["workflow"]["updated_at"] = now_iso()

    save_state(state)

    return state


def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        raise FileNotFoundError(
            "Harness is not initialized. Run 'harness init' first."
        )

    with STATE_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_state(state: dict[str, Any]) -> None:
    ensure_harness_structure()

    state["workflow"]["updated_at"] = now_iso()

    with STATE_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            state,
            file,
            indent=2,
            ensure_ascii=False,
        )
        file.write("\n")
