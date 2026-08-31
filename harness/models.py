"""
Agent result model for the Claude Engineering Harness.
"""

from dataclasses import dataclass, field
from typing import Any


REQUIRED_STRING_FIELDS = ("agent", "stage", "outcome", "summary")


@dataclass
class AgentResult:
    agent: str
    stage: str
    outcome: str
    summary: str
    artifacts: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "stage": self.stage,
            "outcome": self.outcome,
            "summary": self.summary,
            "artifacts": self.artifacts,
            "metadata": self.metadata,
        }


def _require_non_empty_string(data: dict, field_name: str) -> str:
    if field_name not in data:
        raise ValueError(
            f"Agent result is missing required field '{field_name}'."
        )

    value = data[field_name]

    if not isinstance(value, str):
        raise ValueError(
            f"Agent result field '{field_name}' must be a string, "
            f"got {type(value).__name__}."
        )

    value = value.strip()

    if not value:
        raise ValueError(
            f"Agent result field '{field_name}' must not be empty."
        )

    return value


def parse_agent_result(data: Any) -> AgentResult:
    """
    Validate a raw dict (typically loaded from JSON) and build an
    AgentResult. Raises ValueError with a descriptive message on any
    validation failure.
    """

    if not isinstance(data, dict):
        raise ValueError(
            f"Agent result must be a JSON object, got {type(data).__name__}."
        )

    agent = _require_non_empty_string(data, "agent")
    stage = _require_non_empty_string(data, "stage").upper()
    outcome = _require_non_empty_string(data, "outcome").upper()
    summary = _require_non_empty_string(data, "summary")

    artifacts = data.get("artifacts", [])

    if not isinstance(artifacts, list):
        raise ValueError(
            "Agent result field 'artifacts' must be a list when present."
        )

    metadata = data.get("metadata", {})

    if not isinstance(metadata, dict):
        raise ValueError(
            "Agent result field 'metadata' must be an object when present."
        )

    return AgentResult(
        agent=agent,
        stage=stage,
        outcome=outcome,
        summary=summary,
        artifacts=artifacts,
        metadata=metadata,
    )
