# Claude Engineering Harness — Agent Contract

## Purpose

This document defines the communication protocol between agents in the Claude Engineering Harness.

Agents must communicate workflow outcomes through structured artifacts.

Conversational messages are not considered authoritative workflow state.

The authoritative sources are:

1. `.harness/state.json`
2. Stage artifacts
3. Structured agent results
4. Test evidence

---

# Core Principle

Every agent performs one role.

Every agent must produce:

1. A persistent artifact.
2. A structured result.
3. A clear workflow outcome.

No agent may advance the workflow without producing evidence required by its role.

---

# Agent Result Contract

Every agent must produce an Agent Result with the following structure:

```json
{
  "agent": "AGENT_NAME",

  "status": "SUCCESS | FAIL | BLOCKED",

  "current_stage": "STAGE_NAME",

  "recommended_next_stage": "STAGE_NAME",

  "artifact": {
    "path": "path/to/artifact",
    "status": "CREATED | UPDATED | UNCHANGED"
  },

  "summary": "Short summary of the result",

  "evidence": [
    "Evidence item"
  ],

  "issues": [
    {
      "severity": "LOW | MEDIUM | HIGH | CRITICAL",
      "description": "Issue description"
    }
  ],

  "requires_human": false
}
```

---

# Agent Names

Allowed agent values:

* MAESTRO
* SPEC_ENGINEER
* PLANNER
* EXECUTOR
* TESTER
* DEBUGGER
* REVIEWER
* DOCUMENTER

---

# Status Values

## SUCCESS

The agent completed its assigned responsibility successfully.

SUCCESS does not automatically mean the feature is complete.

---

## FAIL

The assigned responsibility produced a negative result.

Examples:

* Tests failed.
* Review failed.
* Required validation failed.

FAIL must include evidence.

---

## BLOCKED

The agent cannot safely continue.

Examples:

* Missing credentials.
* Ambiguous requirement.
* Required infrastructure unavailable.
* Missing dependency.
* Dangerous action requires human approval.

BLOCKED must explain the blocking condition.

---

# Workflow Stages

Allowed values:

* TASK
* SPECIFICATION
* PLANNING
* EXECUTION
* TESTING
* DIAGNOSIS
* FIXING
* REVIEW
* DOCUMENTATION
* COMPLETE

---

# Evidence Rule

No agent may claim a successful validation without evidence.

Examples of valid evidence:

* Test command output.
* Build output.
* Linter output.
* API response.
* Screenshot or captured result when relevant.
* File comparison.
* Log output.

Invalid evidence:

* "It should work."
* "The implementation looks correct."
* "The code seems fine."

---

# Authority Rules

## SPEC_ENGINEER

Authority:

Defines requirements and acceptance criteria.

Cannot:

* Implement production code.
* Mark tests as passed.
* Mark the feature complete.

---

## PLANNER

Authority:

Defines execution order and validation strategy.

Cannot:

* Change requirements.
* Mark implementation complete.
* Mark quality gates as passed.

---

## EXECUTOR

Authority:

Implements code.

Cannot:

* Validate its own implementation.
* Mark the feature complete.
* Override test failures.

---

## TESTER

Authority:

Determines test outcome based on evidence.

Cannot:

* Modify production code.
* Change requirements.

---

## DEBUGGER

Authority:

Determines probable root cause.

Cannot:

* Mark validation as passed.
* Declare the feature complete.

---

## REVIEWER

Authority:

Performs final engineering review.

Can:

* Approve or reject the implementation for documentation.

Cannot:

* Modify production code.

---

## DOCUMENTER

Authority:

Documents validated implementation.

Cannot:

* Document unvalidated behavior.
* Mark incomplete work as COMPLETE.

---

# Workflow Authority

Only MAESTRO may advance the workflow state.

Agents may recommend the next stage.

MAESTRO decides whether the transition is valid.

---

# Failure Loop

When TESTER returns:

```text
STATUS = FAIL
```

The required transition is:

```text
TESTING
→
DIAGNOSIS
→
FIXING
→
EXECUTION
→
TESTING
```

The workflow must not skip TESTING after a fix.

Every fix requires a new validation cycle.

---

# Completion Rule

The workflow can reach COMPLETE only when:

1. All required quality gates pass.
2. Acceptance criteria have evidence.
3. REVIEWER returns PASS.
4. Documentation is updated.
5. FINAL_REPORT exists.

No single agent can bypass these requirements.

---

# Human Escalation

An agent must request human intervention when:

* Requirements are ambiguous.
* Maximum iterations are reached.
* The same root cause repeats three times.
* Required credentials are unavailable.
* A destructive operation is required.
* A security-sensitive decision requires approval.
* The required fix exceeds the approved scope.

When escalation occurs:

```text
requires_human = true
```

MAESTRO must transition the workflow to BLOCKED or ESCALATED.
