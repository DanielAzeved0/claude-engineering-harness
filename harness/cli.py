"""
Command-line interface for the Claude Engineering Harness.
"""

import argparse
import sys
from datetime import datetime

from harness.artifacts import list_artifact_status
from harness.controller import process_result_file, start_task, transition
from harness.roles import build_agent_context, get_role_template_path
from harness.state import initialize_state, load_state
from harness.transitions import get_allowed_outcomes


def print_status() -> None:
    state = load_state()

    workflow = state["workflow"]
    iteration = state["iteration"]

    print()
    print("Claude Engineering Harness")
    print("=" * 32)

    print(f"Status: {workflow['status']}")
    print(f"Current Stage: {workflow['current_stage']}")
    print(f"Previous Stage: {workflow['previous_stage']}")

    print()
    print(f"Iteration: {iteration['current']}/{iteration['max']}")

    task = state["task"]

    print()
    print("Task")
    print(f"ID: {task['id']}")
    print(f"Title: {task['title']}")

    print()
    print("Quality Gates")

    for name, gate in state["quality_gates"].items():
        required = "required" if gate["required"] else "optional"

        print(f"- {name}: {gate['status']} ({required})")

    current_stage = workflow["current_stage"]

    if current_stage:
        allowed = get_allowed_outcomes(current_stage)

        if allowed:
            print()
            print("Allowed Outcomes: " + ", ".join(allowed))

    print()


def _format_history(history: list[dict]) -> list[str]:
    lines = []
    previous_timestamp = None

    for index, entry in enumerate(history, start=1):
        timestamp = entry.get("timestamp")
        delta_str = ""

        if previous_timestamp and timestamp:
            delta = (
                datetime.fromisoformat(timestamp)
                - datetime.fromisoformat(previous_timestamp)
            )
            delta_str = f" (+{delta.total_seconds():.1f}s)"

        from_stage = entry.get("from")
        to_stage = entry.get("to")
        outcome = entry.get("outcome")
        agent = entry.get("agent", "-")
        summary = entry.get("summary", "")

        line = f"{index}. {from_stage} -> {to_stage} [{outcome}] agent={agent} @ {timestamp}{delta_str}"

        if summary:
            line += f"\n   {summary}"

        lines.append(line)
        previous_timestamp = timestamp or previous_timestamp

    return lines


def command_history(_: argparse.Namespace) -> None:
    try:
        state = load_state()
    except FileNotFoundError as error:
        print(f"Error: {error}")
        sys.exit(1)

    history = state["history"]

    print()
    print("Workflow History")
    print("=" * 32)

    if not history:
        print("(no history yet)")
        print()
        return

    for line in _format_history(history):
        print(line)

    print()


def command_artifacts(_: argparse.Namespace) -> None:
    try:
        state = load_state()
    except FileNotFoundError as error:
        print(f"Error: {error}")
        sys.exit(1)

    print()
    print("Artifacts")
    print("=" * 32)

    for status in list_artifact_status(state):
        marker = "present" if status["exists"] else "missing"
        print(f"{status['stage']} ({status['role']}): {status['path']} [{marker}]")

    print()


def command_init(_: argparse.Namespace) -> None:
    try:
        initialize_state()

        print("Harness initialized successfully.")
        print(".harness directory created.")
        print("state.json created.")

    except FileExistsError as error:
        print(f"Error: {error}")
        sys.exit(1)


def command_status(_: argparse.Namespace) -> None:
    try:
        print_status()

    except FileNotFoundError as error:
        print(f"Error: {error}")
        sys.exit(1)


def command_start(args: argparse.Namespace) -> None:
    try:
        start_task(
            task_id=args.task_id,
            title=args.title,
        )

        print("Task started.")
        print(f"ID: {args.task_id}")
        print(f"Title: {args.title}")
        print("Stage: TASK")

    except (FileNotFoundError, ValueError) as error:
        print(f"Error: {error}")
        sys.exit(1)


def command_transition(args: argparse.Namespace) -> None:
    try:
        result = transition(args.outcome)

        print()
        print("Workflow transitioned.")
        print(f"From: {result['from']}")
        print(f"Outcome: {result['outcome']}")
        print(f"To: {result['to']}")
        print(f"Status: {result['status']}")
        print()

    except (FileNotFoundError, ValueError) as error:
        print(f"Error: {error}")
        sys.exit(1)


def command_result(args: argparse.Namespace) -> None:
    print("Processing agent result...")
    print()

    try:
        result = process_result_file(args.result_path)
    except (FileNotFoundError, ValueError) as error:
        print(f"Error: {error}")
        sys.exit(1)

    print(f"Agent: {result['agent']}")
    print(f"Stage: {result['from']}")
    print(f"Outcome: {result['outcome']}")
    print(f"Summary: {result['summary']}")

    print()
    print("Transition:")
    print(f"  {result['from']} -> {result['to']} (via {result['outcome']})")

    print()
    print(f"Workflow status: {result['status']}")
    print()


def command_role(_: argparse.Namespace) -> None:
    try:
        state = load_state()
        context = build_agent_context(state)
    except (FileNotFoundError, ValueError) as error:
        print(f"Error: {error}")
        sys.exit(1)

    print()
    print(f"Stage: {context['stage']}")
    print(f"Role: {context['role']}")
    print(f"Template: {get_role_template_path(context['role'])}")
    print(f"Expected artifact: {context['artifact_path']}")
    print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="harness",
        description="Claude Engineering Harness",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    init_parser = subparsers.add_parser(
        "init",
        help="Initialize the Harness",
    )
    init_parser.set_defaults(func=command_init)

    status_parser = subparsers.add_parser(
        "status",
        help="Show Harness status",
    )
    status_parser.set_defaults(func=command_status)

    start_parser = subparsers.add_parser(
        "start",
        help="Start a new engineering task",
    )

    start_parser.add_argument(
        "task_id",
        help="Unique task identifier",
    )

    start_parser.add_argument(
        "title",
        help="Task title",
    )

    start_parser.set_defaults(func=command_start)

    transition_parser = subparsers.add_parser(
        "transition",
        help="Apply a workflow transition",
    )

    transition_parser.add_argument(
        "outcome",
        help="Workflow outcome",
    )

    transition_parser.set_defaults(func=command_transition)

    result_parser = subparsers.add_parser(
        "result",
        help="Process a structured agent result file",
    )

    result_parser.add_argument(
        "result_path",
        help="Path to the agent result JSON file",
    )

    result_parser.set_defaults(func=command_result)

    role_parser = subparsers.add_parser(
        "role",
        help="Show the role responsible for the current stage",
    )
    role_parser.set_defaults(func=command_role)

    history_parser = subparsers.add_parser(
        "history",
        help="Show workflow history timeline",
    )
    history_parser.set_defaults(func=command_history)

    artifacts_parser = subparsers.add_parser(
        "artifacts",
        help="Show expected artifacts and whether they exist on disk",
    )
    artifacts_parser.set_defaults(func=command_artifacts)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
