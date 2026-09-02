# Bloco A — Iteration Engine, Agent Role System, Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar as três fases do roadmap que não têm dependência real entre si (Fase 3 — Iteration Engine, Fase 5 — Agent Role System, Fase 9 — Observability), estruturadas em três blocos paralelizáveis.

**Architecture:** Cada bloco é um conjunto de tasks que só toca arquivos próprios (ver mapa de arquivos abaixo). Bloco 1 (Fase 3) adiciona `harness/iteration.py` e edita `harness/controller.py`. Bloco 2 (Fase 5) adiciona `harness/roles.py` e um subcomando novo em `harness/cli.py`. Bloco 3 (Fase 9) adiciona outro subcomando novo em `harness/cli.py`. O único ponto de contato entre blocos é `harness/cli.py`, e a mudança de cada bloco lá é puramente aditiva (um bloco de `subparsers.add_parser(...)` novo) — os três blocos podem ser implementados em paralelo (worktrees isolados) e integrados depois com um merge/rebase trivial. Depois que os três blocos estiverem mergeados, rodar a suíte completa uma vez para confirmar que a integração não quebrou nada (não é uma task formal, é a checagem final de merge).

**Tech Stack:** Python 3.10+, stdlib apenas (`unittest`, `hashlib`, `datetime`, `argparse`, `pathlib`) — sem dependências novas.

**Spec:** (aprovada em chat durante o brainstorming; resumo fiel abaixo)

> **Fase 3 — Iteration Engine.** Hoje o ciclo `FIXING → EXECUTION → TESTING → DIAGNOSIS → FIXING` não tem limite — um agente pode ficar preso num loop infinito real. Corrigir incrementando `state.iteration.current` toda vez que o workflow entra em `DIAGNOSIS` (ponto de convergência de `TESTING FAIL` e `EXECUTION FAIL`); se `current > max` (10), forçar `ESCALATED` em vez de `DIAGNOSIS`. Separadamente, quando um resultado de agente do estágio `DIAGNOSIS` leva a `FIXING`, registrar um hash da causa raiz (`metadata.root_cause`, com fallback pro `summary` se ausente); se a mesma causa se repetir ≥3 vezes, forçar `ESCALATED` em vez de `FIXING`. Os dois guards nunca lançam exceção — reescrevem o resultado da transição antes de persistir, populando `state.escalation.reason`.
>
> **Fase 5 — Agent Role System.** Conectar os templates já escritos em `roles/*.md` ao código: mapeamento estágio→papel (já documentado em `AGENTS.md`, só falta codificar), carregamento do template de um papel, e uma função pura `build_agent_context(state)` que monta o contexto que a Fase 6 (Runner, fora de escopo aqui) vai usar depois — task id/title, estágio atual, papel responsável, artefato esperado, resumo do último resultado, iteração atual. Expor um comando `harness role` que imprime papel/estágio/artefato atual — útil mesmo sem Runner, pra um operador humano saber qual papel/prompt usar manualmente. Corrigir a referência desatualizada "Fase 4" em `AGENTS.md:64` para "Fase 5" (renumeração do roadmap).
>
> **Fase 9 — Observability.** Escopo reduzido deliberadamente: métricas de tokens/custo não têm fonte de dados real ainda (dependem do Runner, Fase 6, fora de escopo). Implementar só `harness history` — imprime a timeline de `state.history` (já populada desde a Fase 2) de forma legível: transição, outcome, agente, resumo, timestamp e duração calculada entre entradas consecutivas.

## Global Constraints

- Testes rodam com `python -m unittest discover -s tests -v` (padrão já estabelecido no projeto, ver `ARCHITECTURE.md:183`).
- Depois de cada task, rodar `python -m compileall harness` sem erros (princípio 9 de `PROJECT_CONTEXT.md`: toda funcionalidade importante do controlador precisa de teste automatizado).
- Testes que envolvem `.harness/state.json` isolam-se em `tempfile.mkdtemp()` + `os.chdir()` no `setUp`/`tearDown` (padrão de `tests/test_result_processing.py` e `tests/test_workflow.py`) — nunca tocam o `.harness/` real do desenvolvedor.
- Testes que só precisam ler `roles/*.md` (arquivo estático versionado) **não** fazem `chdir` — rodam a partir da raiz do repo, igual à suíte hoje.
- Sem dependências novas: tudo com stdlib (`hashlib`, `datetime`, `unittest.mock`).
- Fonte da verdade de regras/schema é Python (`harness/*.py`) — não reintroduzir `config/*.json` ou `schemas/*.json` vazios.
- `iteration.max` = 10 (já default no schema, fixo por ora — YAGNI). Threshold de repetição de causa raiz = 3.

---

## Bloco 1 — Fase 3: Iteration Engine

**Arquivos deste bloco:** `harness/iteration.py` (novo), `harness/controller.py` (modifica), `tests/test_iteration.py` (novo), `tests/test_result_processing.py` (adiciona casos). Não toca `harness/cli.py`.

### Task 1: `harness/iteration.py` — funções puras de detecção de loop

**Files:**
- Create: `harness/iteration.py`
- Test: `tests/test_iteration.py`

**Interfaces:**
- Consumes: nada (módulo novo, funções puras sobre dicts)
- Produces: `increment_iteration(state) -> int`, `iteration_limit_exceeded(state) -> bool`, `compute_root_cause_hash(text) -> str`, `register_root_cause(state, text) -> int`, `root_cause_repeated_too_often(count) -> bool`, `ROOT_CAUSE_REPEAT_THRESHOLD = 3` — usados pelo Bloco 1/Task 2 (mesmo bloco, sequencial) em `harness/controller.py`.

- [ ] **Step 1: Escrever os testes (falhando)**

Criar `tests/test_iteration.py`:

```python
"""
Tests for harness.iteration (loop detection helpers).
"""

import unittest

from harness.iteration import (
    ROOT_CAUSE_REPEAT_THRESHOLD,
    compute_root_cause_hash,
    increment_iteration,
    iteration_limit_exceeded,
    register_root_cause,
    root_cause_repeated_too_often,
)


def _make_state(current=0, max_=10, last_hash=None, same_count=0):
    return {
        "iteration": {"current": current, "max": max_},
        "loop_detection": {
            "last_root_cause_hash": last_hash,
            "same_root_cause_count": same_count,
        },
    }


class IncrementIterationTestCase(unittest.TestCase):
    def test_increment_iteration_increases_current(self):
        state = _make_state(current=0)
        result = increment_iteration(state)
        self.assertEqual(result, 1)
        self.assertEqual(state["iteration"]["current"], 1)

    def test_increment_iteration_twice_accumulates(self):
        state = _make_state(current=0)
        increment_iteration(state)
        increment_iteration(state)
        self.assertEqual(state["iteration"]["current"], 2)


class IterationLimitExceededTestCase(unittest.TestCase):
    def test_under_max_is_not_exceeded(self):
        state = _make_state(current=5, max_=10)
        self.assertFalse(iteration_limit_exceeded(state))

    def test_at_max_is_not_exceeded(self):
        state = _make_state(current=10, max_=10)
        self.assertFalse(iteration_limit_exceeded(state))

    def test_over_max_is_exceeded(self):
        state = _make_state(current=11, max_=10)
        self.assertTrue(iteration_limit_exceeded(state))


class ComputeRootCauseHashTestCase(unittest.TestCase):
    def test_same_text_same_hash(self):
        self.assertEqual(
            compute_root_cause_hash("Null pointer in auth"),
            compute_root_cause_hash("Null pointer in auth"),
        )

    def test_hash_ignores_case_and_surrounding_whitespace(self):
        self.assertEqual(
            compute_root_cause_hash("Null Pointer In Auth"),
            compute_root_cause_hash("  null pointer in auth  "),
        )

    def test_different_text_different_hash(self):
        self.assertNotEqual(
            compute_root_cause_hash("cause A"),
            compute_root_cause_hash("cause B"),
        )


class RegisterRootCauseTestCase(unittest.TestCase):
    def test_first_registration_sets_count_to_one(self):
        state = _make_state()
        count = register_root_cause(state, "Null pointer in auth")
        self.assertEqual(count, 1)
        self.assertEqual(state["loop_detection"]["same_root_cause_count"], 1)
        self.assertIsNotNone(state["loop_detection"]["last_root_cause_hash"])

    def test_same_cause_again_increments_count(self):
        state = _make_state()
        register_root_cause(state, "Null pointer in auth")
        count = register_root_cause(state, "Null pointer in auth")
        self.assertEqual(count, 2)

    def test_different_cause_resets_count_to_one(self):
        state = _make_state()
        register_root_cause(state, "Null pointer in auth")
        register_root_cause(state, "Null pointer in auth")
        count = register_root_cause(state, "Different bug entirely")
        self.assertEqual(count, 1)


class RootCauseRepeatedTooOftenTestCase(unittest.TestCase):
    def test_below_threshold_is_false(self):
        self.assertFalse(root_cause_repeated_too_often(ROOT_CAUSE_REPEAT_THRESHOLD - 1))

    def test_at_threshold_is_true(self):
        self.assertTrue(root_cause_repeated_too_often(ROOT_CAUSE_REPEAT_THRESHOLD))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `python -m unittest tests.test_iteration -v`
Expected: FAIL / ERROR — `ModuleNotFoundError: No module named 'harness.iteration'`

- [ ] **Step 3: Implementar `harness/iteration.py`**

```python
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
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `python -m unittest tests.test_iteration -v`
Expected: PASS (12 testes)

- [ ] **Step 5: Compilar e commitar**

```bash
python -m compileall harness
git add harness/iteration.py tests/test_iteration.py
git commit -m "feat: add loop detection helpers (harness.iteration)"
```

---

### Task 2: Integrar os guards em `harness/controller.py`

**Files:**
- Modify: `harness/controller.py:14-38` (`_apply_stage_transition`), `harness/controller.py:41-70` (`transition`), `harness/controller.py:73-145` (`process_result_file`)
- Test: `tests/test_result_processing.py` (adiciona casos ao final da classe `ResultProcessingTestCase`)

**Interfaces:**
- Consumes: `harness.iteration.increment_iteration`, `.iteration_limit_exceeded`, `.register_root_cause`, `.root_cause_repeated_too_often` (Task 1, mesmo bloco)
- Produces: `_apply_stage_transition(state, outcome)` — **assinatura muda** de `(workflow, outcome)` para `(state, outcome)`. Nenhum outro módulo chama essa função privada hoje (confirmado: só é chamada dentro de `controller.py`), então não há callers externos a atualizar.

- [ ] **Step 1: Escrever os testes (falhando)**

Adicionar ao final de `tests/test_result_processing.py`, dentro da classe `ResultProcessingTestCase` (antes de `if __name__ == "__main__":`):

```python
    def test_iteration_increments_on_diagnosis_entry(self):
        self._advance_to_testing()

        result_path = self._write_result(
            "tester-result.json",
            {
                "agent": "tester",
                "stage": "TESTING",
                "outcome": "FAIL",
                "summary": "Simulated test failure",
            },
        )
        process_result_file(result_path)

        state = load_state()
        self.assertEqual(state["iteration"]["current"], 1)

    def test_iteration_limit_forces_escalation(self):
        start_task("T-3", "Task that loops forever")
        transition("SUCCESS")  # TASK -> SPECIFICATION
        transition("SUCCESS")  # SPECIFICATION -> PLANNING
        transition("SUCCESS")  # PLANNING -> EXECUTION

        for _ in range(10):
            transition("FAIL")     # EXECUTION -> DIAGNOSIS
            transition("SUCCESS")  # DIAGNOSIS -> FIXING
            transition("SUCCESS")  # FIXING -> EXECUTION

        state = load_state()
        self.assertEqual(state["iteration"]["current"], 10)
        self.assertEqual(state["workflow"]["current_stage"], "EXECUTION")

        result = transition("FAIL")  # would be the 11th DIAGNOSIS entry

        self.assertEqual(result["to"], "ESCALATED")
        self.assertEqual(result["status"], "ESCALATED")

        state = load_state()
        self.assertTrue(state["escalation"]["required"])
        self.assertIn("Iteration limit", state["escalation"]["reason"])

    def test_repeated_root_cause_forces_escalation(self):
        start_task("T-4", "Task with recurring bug")
        transition("SUCCESS")  # TASK -> SPECIFICATION
        transition("SUCCESS")  # SPECIFICATION -> PLANNING
        transition("SUCCESS")  # PLANNING -> EXECUTION
        transition("FAIL")     # EXECUTION -> DIAGNOSIS

        for i in range(2):
            result_path = self._write_result(
                f"diagnosis-result-{i}.json",
                {
                    "agent": "debugger",
                    "stage": "DIAGNOSIS",
                    "outcome": "SUCCESS",
                    "summary": "Found the bug",
                    "metadata": {"root_cause": "Null pointer in auth middleware"},
                },
            )
            result = process_result_file(result_path)
            self.assertEqual(result["to"], "FIXING")

            transition("FAIL")  # FIXING -> DIAGNOSIS (fix didn't work)

        result_path = self._write_result(
            "diagnosis-result-2.json",
            {
                "agent": "debugger",
                "stage": "DIAGNOSIS",
                "outcome": "SUCCESS",
                "summary": "Found the bug again",
                "metadata": {"root_cause": "Null pointer in auth middleware"},
            },
        )
        result = process_result_file(result_path)

        self.assertEqual(result["to"], "ESCALATED")

        state = load_state()
        self.assertEqual(state["loop_detection"]["same_root_cause_count"], 3)
        self.assertTrue(state["escalation"]["required"])
        self.assertIn("Root cause", state["escalation"]["reason"])

    def test_different_root_causes_do_not_trigger_escalation(self):
        start_task("T-5", "Task with varied bugs")
        transition("SUCCESS")  # TASK -> SPECIFICATION
        transition("SUCCESS")  # SPECIFICATION -> PLANNING
        transition("SUCCESS")  # PLANNING -> EXECUTION
        transition("FAIL")     # EXECUTION -> DIAGNOSIS

        for i in range(5):
            result_path = self._write_result(
                f"diagnosis-varied-{i}.json",
                {
                    "agent": "debugger",
                    "stage": "DIAGNOSIS",
                    "outcome": "SUCCESS",
                    "summary": "Found a bug",
                    "metadata": {"root_cause": f"Cause number {i}"},
                },
            )
            result = process_result_file(result_path)
            self.assertEqual(result["to"], "FIXING")
            transition("FAIL")  # FIXING -> DIAGNOSIS

        state = load_state()
        self.assertEqual(state["loop_detection"]["same_root_cause_count"], 1)
        self.assertFalse(state["escalation"]["required"])

    def test_root_cause_falls_back_to_summary_when_metadata_missing(self):
        start_task("T-6", "Task without metadata")
        transition("SUCCESS")  # TASK -> SPECIFICATION
        transition("SUCCESS")  # SPECIFICATION -> PLANNING
        transition("SUCCESS")  # PLANNING -> EXECUTION
        transition("FAIL")     # EXECUTION -> DIAGNOSIS

        result_path = self._write_result(
            "diagnosis-no-metadata.json",
            {
                "agent": "debugger",
                "stage": "DIAGNOSIS",
                "outcome": "SUCCESS",
                "summary": "Auth middleware null pointer",
            },
        )
        process_result_file(result_path)

        state = load_state()
        self.assertIsNotNone(state["loop_detection"]["last_root_cause_hash"])
        self.assertEqual(state["loop_detection"]["same_root_cause_count"], 1)
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `python -m unittest tests.test_result_processing -v`
Expected: os 5 testes novos falham (`state["iteration"]["current"]` continua `0`; nenhuma escalada acontece) — os testes existentes continuam passando.

- [ ] **Step 3: Modificar `harness/controller.py`**

Adicionar ao topo do arquivo (junto aos imports existentes):

```python
from harness.iteration import (
    increment_iteration,
    iteration_limit_exceeded,
    register_root_cause,
    root_cause_repeated_too_often,
)
```

Substituir a função `_apply_stage_transition` inteira (linhas 14-38) por:

```python
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
```

Em `transition()`, trocar a chamada (linha ~51):

```python
    previous_stage, next_stage = _apply_stage_transition(workflow, outcome)
```

por:

```python
    previous_stage, next_stage = _apply_stage_transition(state, outcome)
```

Em `process_result_file()`, trocar a chamada (linhas ~111-113):

```python
    previous_stage, next_stage = _apply_stage_transition(
        workflow, agent_result.outcome
    )
```

por:

```python
    previous_stage, next_stage = _apply_stage_transition(
        state, agent_result.outcome
    )

    if agent_result.stage == "DIAGNOSIS" and next_stage == "FIXING":
        root_cause = agent_result.metadata.get("root_cause") or agent_result.summary
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
```

(O restante de `process_result_file` — bloco `state["last_result"] = ...` em diante — não muda; ele já usa a variável `next_stage`, que agora pode ter sido sobrescrita para `"ESCALATED"` antes de chegar lá.)

- [ ] **Step 4: Rodar toda a suíte e confirmar que passa**

Run: `python -m unittest discover -s tests -v`
Expected: PASS — todos os testes, incluindo os pré-existentes (`test_transitions.py`, `test_workflow.py`, `test_result_processing.py` completo) e os 5 novos.

- [ ] **Step 5: Compilar e commitar**

```bash
python -m compileall harness
git add harness/controller.py tests/test_result_processing.py
git commit -m "feat: enforce iteration limit and repeated-root-cause escalation"
```

---

## Bloco 2 — Fase 5: Agent Role System

**Arquivos deste bloco:** `harness/roles.py` (novo), `harness/cli.py` (adiciona subcomando `role`), `AGENTS.md` (corrige referência de fase), `tests/test_roles.py` (novo), `tests/test_cli_role.py` (novo). Não toca `harness/controller.py` nem `harness/iteration.py`.

### Task 3: `harness/roles.py` — mapeamento e contexto de agente

**Files:**
- Create: `harness/roles.py`
- Test: `tests/test_roles.py`

**Interfaces:**
- Consumes: nada (módulo novo)
- Produces: `STAGE_ROLE_MAP: dict[str, str]`, `get_role_for_stage(stage) -> str`, `get_role_template_path(role) -> Path`, `load_role_prompt(role) -> str`, `build_agent_context(state) -> dict` — usados pelo Bloco 2/Task 4 (mesmo bloco) em `harness/cli.py`, e futuramente pela Fase 6 (Runner, fora de escopo).

- [ ] **Step 1: Escrever os testes (falhando)**

Criar `tests/test_roles.py`:

```python
"""
Tests for harness.roles.
"""

import unittest

from harness.roles import (
    STAGE_ROLE_MAP,
    build_agent_context,
    get_role_for_stage,
    get_role_template_path,
    load_role_prompt,
)


NON_TERMINAL_STAGES = [
    "TASK", "SPECIFICATION", "PLANNING", "EXECUTION",
    "TESTING", "DIAGNOSIS", "FIXING", "REVIEW", "DOCUMENTATION",
]


class RoleMappingTestCase(unittest.TestCase):
    def test_every_non_terminal_stage_has_a_role(self):
        for stage in NON_TERMINAL_STAGES:
            self.assertIn(stage, STAGE_ROLE_MAP)

    def test_get_role_for_stage_returns_expected_role(self):
        self.assertEqual(get_role_for_stage("TESTING"), "TESTER")

    def test_get_role_for_stage_is_case_insensitive(self):
        self.assertEqual(get_role_for_stage("testing"), "TESTER")

    def test_get_role_for_unknown_stage_raises(self):
        with self.assertRaises(ValueError):
            get_role_for_stage("NOT_A_STAGE")

    def test_every_role_template_file_exists_on_disk(self):
        for stage in NON_TERMINAL_STAGES:
            role = get_role_for_stage(stage)
            template_path = get_role_template_path(role)
            self.assertTrue(
                template_path.is_file(),
                f"Missing template for role {role}: {template_path}",
            )

    def test_load_role_prompt_returns_file_content(self):
        content = load_role_prompt("TESTER")
        self.assertIn("TESTER", content.upper())


class BuildAgentContextTestCase(unittest.TestCase):
    def _make_state(self, stage):
        return {
            "workflow": {"current_stage": stage},
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
            "task": {"id": "T-1", "title": "Sample task"},
            "iteration": {"current": 2, "max": 10},
            "last_result": {"agent": None, "status": None, "summary": None},
        }

    def test_build_agent_context_for_testing_stage(self):
        state = self._make_state("TESTING")
        context = build_agent_context(state)

        self.assertEqual(context["stage"], "TESTING")
        self.assertEqual(context["role"], "TESTER")
        self.assertEqual(context["artifact_path"], ".harness/tests/TEST_RESULTS.json")
        self.assertEqual(context["task_id"], "T-1")
        self.assertEqual(context["iteration"], 2)

    def test_build_agent_context_without_active_stage_raises(self):
        state = self._make_state(None)
        with self.assertRaises(ValueError):
            build_agent_context(state)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `python -m unittest tests.test_roles -v`
Expected: FAIL / ERROR — `ModuleNotFoundError: No module named 'harness.roles'`

- [ ] **Step 3: Implementar `harness/roles.py`**

```python
"""
Agent role definitions for the Claude Engineering Harness.
"""

from pathlib import Path
from typing import Any


ROLES_DIR = Path("roles")


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
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `python -m unittest tests.test_roles -v`
Expected: PASS (7 testes). Rodar a partir da raiz do repositório (sem `chdir` para tempdir) — `load_role_prompt`/`get_role_template_path` leem `roles/*.md` relativos ao cwd.

- [ ] **Step 5: Compilar e commitar**

```bash
python -m compileall harness
git add harness/roles.py tests/test_roles.py
git commit -m "feat: add stage-to-role mapping and agent context builder"
```

---

### Task 4: CLI `harness role` + correção de doc

**Files:**
- Modify: `harness/cli.py` (import, nova função `command_role`, novo subparser em `build_parser`)
- Modify: `AGENTS.md:64`
- Test: `tests/test_cli_role.py`

**Interfaces:**
- Consumes: `harness.roles.build_agent_context`, `.get_role_template_path` (Task 3, mesmo bloco)
- Produces: `command_role(args)` — não consumido por nenhuma outra task deste plano.

- [ ] **Step 1: Escrever o teste (falhando)**

Criar `tests/test_cli_role.py`:

```python
"""
Tests for the `harness role` CLI command.
"""

import os
import shutil
import tempfile
import unittest
from io import StringIO
from unittest.mock import patch

from harness.cli import command_role
from harness.controller import start_task
from harness.state import initialize_state


class RoleCommandTestCase(unittest.TestCase):
    def setUp(self):
        self._original_cwd = os.getcwd()
        self._temp_dir = tempfile.mkdtemp(prefix="harness-test-")
        os.chdir(self._temp_dir)
        initialize_state()

    def tearDown(self):
        os.chdir(self._original_cwd)
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    def test_role_command_prints_role_for_current_stage(self):
        start_task("T-1", "Sample task")

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            command_role(None)

        output = mock_stdout.getvalue()
        self.assertIn("Stage: TASK", output)
        self.assertIn("Role: MAESTRO", output)

    def test_role_command_without_active_task_errors(self):
        with self.assertRaises(SystemExit):
            command_role(None)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `python -m unittest tests.test_cli_role -v`
Expected: FAIL — `ImportError: cannot import name 'command_role' from 'harness.cli'`

- [ ] **Step 3: Implementar em `harness/cli.py`**

Adicionar ao import existente do topo (linha 10, junto a `from harness.transitions import get_allowed_outcomes`):

```python
from harness.roles import build_agent_context, get_role_template_path
```

Adicionar nova função, logo após `command_result` (antes de `def build_parser()`):

```python
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
```

Adicionar o subparser em `build_parser()`, logo antes de `return parser`:

```python
    role_parser = subparsers.add_parser(
        "role",
        help="Show the role responsible for the current stage",
    )
    role_parser.set_defaults(func=command_role)
```

- [ ] **Step 4: Corrigir `AGENTS.md:64`**

Trocar:

```
Esse mapeamento ainda não está codificado em `harness/*.py` — é a base conceitual para a Fase 4.
```

por:

```
Esse mapeamento ainda não está codificado em `harness/*.py` — é a base conceitual para a Fase 5.
```

- [ ] **Step 5: Rodar o teste e confirmar que passa**

Run: `python -m unittest tests.test_cli_role -v`
Expected: PASS (2 testes)

- [ ] **Step 6: Compilar e commitar**

```bash
python -m compileall harness
git add harness/cli.py tests/test_cli_role.py AGENTS.md
git commit -m "feat: add harness role CLI command"
```

---

## Bloco 3 — Fase 9: Observability

**Arquivos deste bloco:** `harness/cli.py` (adiciona subcomando `history`), `tests/test_cli_history.py` (novo). Não toca `harness/controller.py`, `harness/iteration.py` nem `harness/roles.py`.

> **Nota de merge:** este bloco e o Bloco 2/Task 4 tocam `harness/cli.py`, cada um só adicionando um bloco de código próprio (import + função + subparser). Implementar em worktrees separados é seguro; ao integrar, aplicar os dois diffs em sequência (a ordem não importa, nenhum dos dois edita a mesma linha do outro).

### Task 5: CLI `harness history`

**Files:**
- Modify: `harness/cli.py` (nova função `_format_history`, nova função `command_history`, novo subparser em `build_parser`)
- Test: `tests/test_cli_history.py`

**Interfaces:**
- Consumes: `state["history"]` (já produzido desde a Fase 2 por `harness/controller.py`)
- Produces: `_format_history(history) -> list[str]`, `command_history(args)` — não consumidos por nenhuma outra task deste plano.

- [ ] **Step 1: Escrever os testes (falhando)**

Criar `tests/test_cli_history.py`:

```python
"""
Tests for the `harness history` CLI command.
"""

import os
import shutil
import tempfile
import unittest
from io import StringIO
from unittest.mock import patch

from harness.cli import _format_history, command_history
from harness.controller import start_task, transition
from harness.state import initialize_state


class FormatHistoryTestCase(unittest.TestCase):
    def test_format_history_includes_transition_and_outcome(self):
        history = [
            {
                "type": "start",
                "from": None,
                "outcome": "START",
                "to": "TASK",
                "timestamp": "2026-09-01T10:00:00+00:00",
            },
            {
                "type": "manual",
                "from": "TASK",
                "outcome": "SUCCESS",
                "to": "SPECIFICATION",
                "timestamp": "2026-09-01T10:00:05+00:00",
            },
        ]

        lines = _format_history(history)

        self.assertEqual(len(lines), 2)
        self.assertIn("TASK -> SPECIFICATION", lines[1])
        self.assertIn("+5.0s", lines[1])

    def test_format_history_empty_list(self):
        self.assertEqual(_format_history([]), [])

    def test_format_history_handles_missing_agent_key(self):
        history = [
            {
                "type": "manual",
                "from": "TASK",
                "outcome": "SUCCESS",
                "to": "SPECIFICATION",
                "timestamp": "2026-09-01T10:00:00+00:00",
            }
        ]

        lines = _format_history(history)

        self.assertIn("agent=-", lines[0])


class HistoryCommandTestCase(unittest.TestCase):
    def setUp(self):
        self._original_cwd = os.getcwd()
        self._temp_dir = tempfile.mkdtemp(prefix="harness-test-")
        os.chdir(self._temp_dir)
        initialize_state()

    def tearDown(self):
        os.chdir(self._original_cwd)
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    def test_history_command_prints_entries(self):
        start_task("T-1", "Sample task")
        transition("SUCCESS")

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            command_history(None)

        output = mock_stdout.getvalue()
        self.assertIn("TASK -> SPECIFICATION", output)

    def test_history_command_with_no_task_shows_placeholder(self):
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            command_history(None)

        output = mock_stdout.getvalue()
        self.assertIn("no history yet", output)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `python -m unittest tests.test_cli_history -v`
Expected: FAIL — `ImportError: cannot import name '_format_history' from 'harness.cli'`

- [ ] **Step 3: Implementar em `harness/cli.py`**

Adicionar ao import existente do topo (junto aos demais imports do topo do arquivo):

```python
from datetime import datetime
```

Adicionar as duas funções novas, logo após `command_result` (antes de `def build_parser()`):

```python
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

        line = f"{index}. {from_stage} -> {to_stage} [{outcome}] agent={agent}{delta_str}"

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
```

Adicionar o subparser em `build_parser()`, logo antes de `return parser`:

```python
    history_parser = subparsers.add_parser(
        "history",
        help="Show the workflow history timeline",
    )
    history_parser.set_defaults(func=command_history)
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `python -m unittest tests.test_cli_history -v`
Expected: PASS (5 testes)

- [ ] **Step 5: Compilar e commitar**

```bash
python -m compileall harness
git add harness/cli.py tests/test_cli_history.py
git commit -m "feat: add harness history CLI command"
```

---

## Self-Review (feito ao escrever este plano)

**Cobertura da spec:**
- Fase 3: incremento de iteração ao entrar em DIAGNOSIS ✅ Task 2 · limite força ESCALATED ✅ Task 2 · hash de causa raiz com fallback pro summary ✅ Task 1+2 · threshold=3 força ESCALATED ✅ Task 2 · guards nunca lançam exceção ✅ (reescrevem `next_stage` antes de persistir).
- Fase 5: mapeamento estágio→papel ✅ Task 3 · carregar template ✅ Task 3 · `build_agent_context` ✅ Task 3 · comando `harness role` ✅ Task 4 · correção de doc ✅ Task 4.
- Fase 9: `harness history` com timeline, outcome, agente, resumo, duração ✅ Task 5. Tokens/custo explicitamente fora de escopo (sem fonte de dados).

**Placeholders:** nenhum "TBD"/"implementar depois" — todo step tem código completo.

**Consistência de tipos:** `_apply_stage_transition(state, outcome)` usado de forma consistente nas duas chamadas (Task 2); `build_agent_context(state)` retorna as mesmas chaves usadas em `command_role` (Task 3→4); `_format_history(history)` retorna `list[str]`, consumido igual em `command_history` (Task 5).
