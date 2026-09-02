"""
Artifact tracking and execution reporting for the Claude Engineering Harness.
"""

from pathlib import Path
from typing import Any

from harness.roles import STAGE_ARTIFACT_KEY, get_role_for_stage
from harness.state import now_iso


EXECUTION_REPORT_PATH = Path(".harness/reports/EXECUTION_REPORT.md")


def artifact_exists_for_stage(state: dict[str, Any], stage: str) -> bool:
    artifact_key = STAGE_ARTIFACT_KEY[stage]
    path = Path(state["artifacts"][artifact_key])
    return path.is_file()


def list_artifact_status(state: dict[str, Any]) -> list[dict[str, Any]]:
    statuses = []

    for stage, artifact_key in STAGE_ARTIFACT_KEY.items():
        path = state["artifacts"][artifact_key]

        statuses.append(
            {
                "stage": stage,
                "role": get_role_for_stage(stage),
                "path": path,
                "exists": Path(path).is_file(),
            }
        )

    return statuses


def generate_execution_report(state: dict[str, Any]) -> str:
    task = state["task"]

    lines = [
        "# Execution Report",
        "",
        "## Task",
        "",
        f"- ID: {task['id']}",
        f"- Title: {task['title']}",
        f"- Started: {task['created_at']}",
        f"- Generated: {now_iso()}",
        "",
        "## Timeline",
        "",
    ]

    for index, entry in enumerate(state["history"], start=1):
        from_stage = entry.get("from")
        to_stage = entry.get("to")
        outcome = entry.get("outcome")
        agent = entry.get("agent", "-")
        summary = entry.get("summary", "")
        timestamp = entry.get("timestamp", "")

        lines.append(
            f"{index}. {from_stage} -> {to_stage} [{outcome}] "
            f"agent={agent} @ {timestamp}"
        )

        if summary:
            lines.append(f"   {summary}")

    lines += [
        "",
        "## Artifacts",
        "",
        "| Stage | Role | Path | Status |",
        "|---|---|---|---|",
    ]

    for status in list_artifact_status(state):
        marker = "present" if status["exists"] else "missing"
        lines.append(
            f"| {status['stage']} | {status['role']} | {status['path']} | {marker} |"
        )

    quality_gates = state["quality_gates"]
    lines += ["", "## Quality Gates", ""]

    for name, gate in quality_gates.items():
        required = "required" if gate["required"] else "optional"
        lines.append(f"- {name}: {gate['status']} ({required})")

    iteration = state["iteration"]
    escalation = state["escalation"]
    lines += [
        "",
        "## Iterations",
        "",
        f"- Count: {iteration['current']}/{iteration['max']}",
        f"- Escalated: {'yes' if escalation['required'] else 'no'}",
    ]

    if escalation["required"]:
        lines.append(f"- Escalation reason: {escalation['reason']}")

    lines.append("")

    return "\n".join(lines)
