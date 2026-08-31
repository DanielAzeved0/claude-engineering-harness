"""
Workflow transition rules for the Claude Engineering Harness.
"""

TRANSITIONS = {
    "TASK": {
        "SUCCESS": "SPECIFICATION",
        "FAIL": "BLOCKED",
    },
    "SPECIFICATION": {
        "SUCCESS": "PLANNING",
        "FAIL": "BLOCKED",
    },
    "PLANNING": {
        "SUCCESS": "EXECUTION",
        "FAIL": "BLOCKED",
    },
    "EXECUTION": {
        "SUCCESS": "TESTING",
        "FAIL": "DIAGNOSIS",
    },
    "TESTING": {
        "PASS": "REVIEW",
        "FAIL": "DIAGNOSIS",
    },
    "DIAGNOSIS": {
        "SUCCESS": "FIXING",
        "FAIL": "ESCALATED",
    },
    "FIXING": {
        "SUCCESS": "EXECUTION",
        "FAIL": "DIAGNOSIS",
    },
    "REVIEW": {
        "PASS": "DOCUMENTATION",
        "FAIL": "DIAGNOSIS",
    },
    "DOCUMENTATION": {
        "SUCCESS": "COMPLETE",
        "FAIL": "BLOCKED",
    },
}


TERMINAL_STAGES = {
    "COMPLETE",
    "BLOCKED",
    "ESCALATED",
}


def get_next_stage(current_stage: str, outcome: str) -> str:
    current_stage = current_stage.upper()
    outcome = outcome.upper()

    if current_stage in TERMINAL_STAGES:
        raise ValueError(
            f"Cannot transition from terminal stage '{current_stage}'."
        )

    if current_stage not in TRANSITIONS:
        raise ValueError(
            f"Unknown workflow stage '{current_stage}'."
        )

    available_transitions = TRANSITIONS[current_stage]

    if outcome not in available_transitions:
        allowed = ", ".join(available_transitions.keys())

        raise ValueError(
            f"Outcome '{outcome}' is not valid for stage "
            f"'{current_stage}'. Allowed outcomes: {allowed}"
        )

    return available_transitions[outcome]


def get_allowed_outcomes(current_stage: str) -> list[str]:
    current_stage = current_stage.upper()

    if current_stage not in TRANSITIONS:
        return []

    return list(TRANSITIONS[current_stage].keys())
