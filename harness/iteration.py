"""
Loop detection and iteration limiting for the Claude Engineering Harness.
"""

import hashlib
from typing import Any


ROOT_CAUSE_REPEAT_THRESHOLD = 3


def increment_iteration(state: dict[str, Any]) -> int:
    state["iteration"]["current"] += 1
    return state["iteration"]["current"]


def iteration_limit_exceeded(state: dict[str, Any]) -> bool:
    iteration = state["iteration"]
    return iteration["current"] > iteration["max"]


def compute_root_cause_hash(root_cause: str) -> str:
    normalized = root_cause.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def register_root_cause(state: dict[str, Any], root_cause: str) -> int:
    loop_detection = state["loop_detection"]
    new_hash = compute_root_cause_hash(root_cause)

    if loop_detection["last_root_cause_hash"] == new_hash:
        loop_detection["same_root_cause_count"] += 1
    else:
        loop_detection["last_root_cause_hash"] = new_hash
        loop_detection["same_root_cause_count"] = 1

    return loop_detection["same_root_cause_count"]


def root_cause_repeated_too_often(count: int) -> bool:
    return count >= ROOT_CAUSE_REPEAT_THRESHOLD
