# Fase 4 — Artifact and Report System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rastreabilidade completa de engenharia — saber a qualquer momento quais artefatos esperados existem no disco, e gerar automaticamente um relatório mecânico e sempre-preciso da execução ao chegar em `COMPLETE`, sem depender de nenhum agente lembrar de escrevê-lo.

**Architecture:** Novo módulo `harness/artifacts.py` (funções puras, reaproveita `STAGE_ARTIFACT_KEY`/`get_role_for_stage` de `harness/roles.py`, sem duplicar o mapeamento estágio→artefato) + integração em `harness/controller.py::_apply_stage_transition` (mesmo ponto central que já concentra os efeitos colaterais de transição desde a Fase 3) + novo comando `harness artifacts` em `harness/cli.py`. Três tasks sequenciais (uma trilha só, sem sub-blocos paralelos): `artifacts.py` → integração no controller → comando CLI, cada uma consumindo a anterior.

**Tech Stack:** Python 3.10+, stdlib apenas (`pathlib`, `unittest`, `unittest.mock`) — sem dependências novas.

**Spec:** (aprovada em chat durante o brainstorming; resumo fiel abaixo)

> Novo módulo `harness/artifacts.py`: `EXECUTION_REPORT_PATH = Path(".harness/reports/EXECUTION_REPORT.md")` — deliberadamente separado de `state["artifacts"]["final_report"]` (`.harness/reports/FINAL_REPORT.md`, que é o entregável do papel DOCUMENTER com estrutura narrativa e julgamento — `roles/documenter.md`). Os dois relatórios são complementares, nunca o mesmo arquivo. `artifact_exists_for_stage(state, stage) -> bool` checa se o artefato esperado do estágio existe no disco. `list_artifact_status(state) -> list[dict]` lista os 9 estágios não-terminais com papel, caminho esperado e se existe. `generate_execution_report(state) -> str` gera markdown mecânico (task, timeline de `state.history`, tabela de artefatos, quality gates, iteração/escalonamento) — função pura, sem I/O.
>
> Em `controller.py`: `process_result_file` grava `artifact_present: bool` na entrada de histórico de cada resultado de agente processado (checagem contra o artefato esperado do estágio do resultado). `_apply_stage_transition` — quando o `next_stage` calculado é `COMPLETE` (cobre tanto `harness transition` manual quanto resultado de agente, os dois já passam por essa função) — gera o relatório e escreve em `EXECUTION_REPORT_PATH`. Nenhuma validação bloqueia a transição — `artifact_present: false` é só um sinal registrado, o objetivo é rastreabilidade, não enforcement.
>
> Novo comando `harness artifacts`: lista os 9 estágios com papel responsável, caminho esperado e se existe no disco agora. Não exige task ativa (os caminhos são fixos, independentes do estado).

## Global Constraints

- Testes rodam com `python -m unittest discover -s tests -v` (padrão do projeto, ver `ARCHITECTURE.md:183`).
- Depois de cada task, rodar `python -m compileall harness` sem erros.
- Testes que envolvem `.harness/state.json` isolam-se em `tempfile.mkdtemp()` + `os.chdir()` no `setUp`/`tearDown` (padrão de `tests/test_result_processing.py`).
- Sem dependências novas: tudo com stdlib.
- `EXECUTION_REPORT.md` e `FINAL_REPORT.md` são arquivos **distintos** — nenhum código desta fase deve escrever em `state["artifacts"]["final_report"]` (`.harness/reports/FINAL_REPORT.md`).
- Marcador de presença de artefato, em texto (CLI e relatório): `"present"` / `"missing"` — sem símbolos Unicode (evita problemas de encoding no console do Windows).

---

### Task 1: `harness/artifacts.py` — status de artefatos e geração de relatório

**Files:**
- Create: `harness/artifacts.py`
- Test: `tests/test_artifacts.py`

**Interfaces:**
- Consumes: `harness.roles.STAGE_ARTIFACT_KEY` (dict estágio→chave de artefato), `harness.roles.get_role_for_stage(stage) -> str`, `harness.state.now_iso() -> str` — todos já existem.
- Produces: `EXECUTION_REPORT_PATH: Path`, `artifact_exists_for_stage(state, stage) -> bool`, `list_artifact_status(state) -> list[dict]`, `generate_execution_report(state) -> str` — usados pela Task 2 (`controller.py`) e Task 3 (`cli.py`).

- [ ] **Step 1: Escrever os testes (falhando)**

Criar `tests/test_artifacts.py`:

```python
"""
Tests for harness.artifacts.
"""

import tempfile
import unittest
from pathlib import Path

from harness.artifacts import (
    artifact_exists_for_stage,
    generate_execution_report,
    list_artifact_status,
)


def _make_state(artifact_overrides=None, history=None, escalation=None):
    artifacts = {
        "task": ".harness/task/TASK.md",
        "spec": ".harness/spec/SPEC.md",
        "plan": ".harness/plan/PLAN.md",
        "execution_log": ".harness/execution/EXECUTION_LOG.md",
        "test_results": ".harness/tests/TEST_RESULTS.json",
        "diagnosis": ".harness/diagnosis/DIAGNOSIS.md",
        "review": ".harness/review/REVIEW.md",
        "final_report": ".harness/reports/FINAL_REPORT.md",
    }

    if artifact_overrides:
        artifacts.update(artifact_overrides)

    return {
        "task": {
            "id": "T-1",
            "title": "Sample task",
            "created_at": "2026-09-01T10:00:00+00:00",
        },
        "artifacts": artifacts,
        "history": history if history is not None else [],
        "quality_gates": {
            "build": {"required": True, "status": "PENDING"},
        },
        "iteration": {"current": 2, "max": 10},
        "escalation": escalation if escalation is not None else {
            "required": False,
            "reason": None,
        },
    }


class ArtifactExistsForStageTestCase(unittest.TestCase):
    def test_missing_artifact_returns_false(self):
        state = _make_state()
        self.assertFalse(artifact_exists_for_stage(state, "SPECIFICATION"))

    def test_existing_artifact_returns_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "SPEC.md"
            path.write_text("content", encoding="utf-8")
            state = _make_state({"spec": str(path)})
            self.assertTrue(artifact_exists_for_stage(state, "SPECIFICATION"))


class ListArtifactStatusTestCase(unittest.TestCase):
    def test_returns_all_nine_stages_in_workflow_order(self):
        state = _make_state()
        statuses = list_artifact_status(state)

        self.assertEqual(len(statuses), 9)
        self.assertEqual(statuses[0]["stage"], "TASK")
        self.assertEqual(statuses[0]["role"], "MAESTRO")
        self.assertFalse(statuses[0]["exists"])
        self.assertEqual(statuses[-1]["stage"], "DOCUMENTATION")

    def test_marks_existing_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "SPEC.md"
            path.write_text("content", encoding="utf-8")
            state = _make_state({"spec": str(path)})

            statuses = list_artifact_status(state)
            spec_status = next(s for s in statuses if s["stage"] == "SPECIFICATION")
            self.assertTrue(spec_status["exists"])


class GenerateExecutionReportTestCase(unittest.TestCase):
    def test_report_includes_task_and_timeline(self):
        state = _make_state(
            history=[
                {
                    "type": "start",
                    "from": None,
                    "outcome": "START",
                    "to": "TASK",
                    "timestamp": "2026-09-01T10:00:00+00:00",
                }
            ]
        )

        report = generate_execution_report(state)

        self.assertIn("T-1", report)
        self.assertIn("Sample task", report)
        self.assertIn("None -> TASK", report)
        self.assertIn("## Artifacts", report)
        self.assertIn("## Quality Gates", report)
        self.assertIn("## Iterations", report)

    def test_report_lists_artifact_presence(self):
        state = _make_state()

        report = generate_execution_report(state)

        self.assertIn("missing", report)

    def test_report_shows_escalation_reason_when_escalated(self):
        state = _make_state(
            escalation={
                "required": True,
                "reason": "Iteration limit reached (10).",
            }
        )

        report = generate_execution_report(state)

        self.assertIn("Escalated: yes", report)
        self.assertIn("Iteration limit reached (10).", report)

    def test_report_does_not_raise_on_empty_history(self):
        state = _make_state()
        report = generate_execution_report(state)
        self.assertIn("# Execution Report", report)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `python -m unittest tests.test_artifacts -v`
Expected: FAIL / ERROR — `ModuleNotFoundError: No module named 'harness.artifacts'`

- [ ] **Step 3: Implementar `harness/artifacts.py`**

```python
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
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `python -m unittest tests.test_artifacts -v`
Expected: PASS (9 testes)

- [ ] **Step 5: Compilar e commitar**

```bash
python -m compileall harness
git add harness/artifacts.py tests/test_artifacts.py
git commit -m "feat: add artifact status tracking and execution report generation"
```

---

### Task 2: Integrar em `harness/controller.py`

**Files:**
- Modify: `harness/controller.py:9-17` (imports), `harness/controller.py:56-61` (`_apply_stage_transition`), `harness/controller.py:159-172` (`process_result_file`)
- Test: `tests/test_result_processing.py` (adiciona casos ao final da classe `ResultProcessingTestCase`)

**Interfaces:**
- Consumes: `harness.artifacts.EXECUTION_REPORT_PATH`, `.artifact_exists_for_stage(state, stage)`, `.generate_execution_report(state)` (Task 1)
- Produces: nada de novo exportado — só efeitos colaterais (campo novo no histórico, arquivo novo em disco) consumidos pela Task 3 indiretamente (o comando `harness artifacts` lê `state["artifacts"]`/disco diretamente, não depende de nada exportado por esta task).

- [ ] **Step 1: Escrever os testes (falhando)**

Adicionar ao final de `tests/test_result_processing.py`, dentro da classe `ResultProcessingTestCase` (antes de `if __name__ == "__main__":`), e adicionar `from pathlib import Path` ao topo do arquivo se ainda não estiver importado (já está, usado por `_write_result`):

```python
    def test_artifact_present_recorded_in_history(self):
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
        history_entry = state["history"][-1]
        self.assertIn("artifact_present", history_entry)
        self.assertFalse(history_entry["artifact_present"])

    def test_artifact_present_true_when_file_exists(self):
        self._advance_to_testing()

        Path(".harness/tests").mkdir(parents=True, exist_ok=True)
        Path(".harness/tests/TEST_RESULTS.json").write_text("{}", encoding="utf-8")

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
        self.assertTrue(state["history"][-1]["artifact_present"])

    def test_execution_report_generated_on_complete(self):
        start_task("T-7", "Task that completes")
        transition("SUCCESS")  # TASK -> SPECIFICATION
        transition("SUCCESS")  # SPECIFICATION -> PLANNING
        transition("SUCCESS")  # PLANNING -> EXECUTION
        transition("SUCCESS")  # EXECUTION -> TESTING
        transition("PASS")     # TESTING -> REVIEW
        transition("PASS")     # REVIEW -> DOCUMENTATION
        transition("SUCCESS")  # DOCUMENTATION -> COMPLETE

        report_path = Path(".harness/reports/EXECUTION_REPORT.md")
        self.assertTrue(report_path.is_file())

        content = report_path.read_text(encoding="utf-8")
        self.assertIn("T-7", content)
        self.assertIn("# Execution Report", content)

    def test_execution_report_does_not_overwrite_final_report(self):
        final_report_path = Path(".harness/reports/FINAL_REPORT.md")
        final_report_path.parent.mkdir(parents=True, exist_ok=True)
        final_report_path.write_text("DOCUMENTER content", encoding="utf-8")

        start_task("T-8", "Task with documenter content")
        transition("SUCCESS")  # TASK -> SPECIFICATION
        transition("SUCCESS")  # SPECIFICATION -> PLANNING
        transition("SUCCESS")  # PLANNING -> EXECUTION
        transition("SUCCESS")  # EXECUTION -> TESTING
        transition("PASS")     # TESTING -> REVIEW
        transition("PASS")     # REVIEW -> DOCUMENTATION
        transition("SUCCESS")  # DOCUMENTATION -> COMPLETE

        self.assertEqual(
            final_report_path.read_text(encoding="utf-8"), "DOCUMENTER content"
        )
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `python -m unittest tests.test_result_processing -v`
Expected: os 4 testes novos falham (`artifact_present` ausente do histórico; `EXECUTION_REPORT.md` nunca é criado) — os testes existentes continuam passando.

- [ ] **Step 3: Modificar `harness/controller.py`**

Adicionar ao import existente do topo (junto ao import de `harness.iteration`):

```python
from harness.artifacts import (
    EXECUTION_REPORT_PATH,
    artifact_exists_for_stage,
    generate_execution_report,
)
```

Em `_apply_stage_transition`, adicionar a geração do relatório logo antes do `return` final:

```python
    workflow["previous_stage"] = current_stage
    workflow["current_stage"] = next_stage
    workflow["status"] = next_stage if next_stage in TERMINAL_STAGES else "RUNNING"

    if next_stage == "COMPLETE":
        EXECUTION_REPORT_PATH.write_text(
            generate_execution_report(state), encoding="utf-8"
        )

    return current_stage, next_stage
```

(`.harness/reports/` já existe — é criado por `ensure_harness_structure()` desde a Fase 1, chamada por `save_state()`/`initialize_state()` antes de qualquer transição ser possível.)

Em `process_result_file`, na entrada de histórico (dict literal que hoje tem `"type": "agent_result"`, ...), adicionar o campo `artifact_present` logo após `"summary"`:

```python
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
```

- [ ] **Step 4: Rodar toda a suíte e confirmar que passa**

Run: `python -m unittest discover -s tests -v`
Expected: PASS — todos os testes, incluindo os pré-existentes e os 4 novos.

- [ ] **Step 5: Compilar e commitar**

```bash
python -m compileall harness
git add harness/controller.py tests/test_result_processing.py
git commit -m "feat: record artifact presence in history and generate execution report on COMPLETE"
```

---

### Task 3: CLI `harness artifacts`

**Files:**
- Modify: `harness/cli.py` (import, nova função `command_artifacts`, novo subparser em `build_parser`)
- Test: `tests/test_cli_artifacts.py`

**Interfaces:**
- Consumes: `harness.artifacts.list_artifact_status(state)` (Task 1)
- Produces: `command_artifacts(args)` — não consumido por nenhuma outra task deste plano.

- [ ] **Step 1: Escrever os testes (falhando)**

Criar `tests/test_cli_artifacts.py`:

```python
"""
Tests for the `harness artifacts` CLI command.
"""

import os
import shutil
import tempfile
import unittest
from io import StringIO
from unittest.mock import patch

from harness.cli import command_artifacts
from harness.state import initialize_state


class ArtifactsCommandTestCase(unittest.TestCase):
    def setUp(self):
        self._original_cwd = os.getcwd()
        self._temp_dir = tempfile.mkdtemp(prefix="harness-test-")
        os.chdir(self._temp_dir)
        initialize_state()

    def tearDown(self):
        os.chdir(self._original_cwd)
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    def test_artifacts_command_lists_all_stages(self):
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            command_artifacts(None)

        output = mock_stdout.getvalue()
        self.assertIn("TASK", output)
        self.assertIn("MAESTRO", output)
        self.assertIn("DOCUMENTATION", output)
        self.assertIn("missing", output)

    def test_artifacts_command_marks_existing_file(self):
        os.makedirs(".harness/spec", exist_ok=True)
        with open(".harness/spec/SPEC.md", "w", encoding="utf-8") as f:
            f.write("content")

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            command_artifacts(None)

        output = mock_stdout.getvalue()
        lines = [line for line in output.splitlines() if "SPECIFICATION" in line]
        self.assertTrue(lines)
        self.assertIn("present", lines[0])

    def test_artifacts_command_works_without_active_task(self):
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            command_artifacts(None)

        output = mock_stdout.getvalue()
        self.assertIn("Artifacts", output)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `python -m unittest tests.test_cli_artifacts -v`
Expected: FAIL — `ImportError: cannot import name 'command_artifacts' from 'harness.cli'`

- [ ] **Step 3: Implementar em `harness/cli.py`**

Adicionar ao import existente do topo (junto a `from harness.roles import build_agent_context, get_role_template_path`):

```python
from harness.artifacts import list_artifact_status
```

Adicionar nova função, logo após `command_history` (antes de `def command_init`):

```python
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
```

Adicionar o subparser em `build_parser()`, logo antes de `return parser`:

```python
    artifacts_parser = subparsers.add_parser(
        "artifacts",
        help="Show expected artifacts and whether they exist on disk",
    )
    artifacts_parser.set_defaults(func=command_artifacts)
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `python -m unittest tests.test_cli_artifacts -v`
Expected: PASS (3 testes)

- [ ] **Step 5: Rodar toda a suíte, compilar e commitar**

```bash
python -m unittest discover -s tests -v
python -m compileall harness
git add harness/cli.py tests/test_cli_artifacts.py
git commit -m "feat: add harness artifacts CLI command"
```

---

## Self-Review (feito ao escrever este plano)

**Cobertura da spec:**
- `artifact_exists_for_stage`/`list_artifact_status`/`generate_execution_report` ✅ Task 1.
- `artifact_present` no histórico ✅ Task 2. `EXECUTION_REPORT.md` gerado em `COMPLETE` (manual e via agente, os dois passam por `_apply_stage_transition`) ✅ Task 2. Nunca sobrescreve `FINAL_REPORT.md` ✅ Task 2 (teste dedicado). Validação não bloqueia transição ✅ (nenhum guard de rejeição foi adicionado, só o campo informativo).
- `harness artifacts` ✅ Task 3, funciona sem task ativa ✅ (teste dedicado).

**Placeholders:** nenhum "TBD"/"implementar depois" — todo step tem código completo.

**Consistência de tipos:** `list_artifact_status(state) -> list[dict]` usado de forma idêntica em `generate_execution_report` (Task 1) e `command_artifacts` (Task 3) — mesmas chaves (`stage`, `role`, `path`, `exists`). Marcador texto `"present"`/`"missing"` usado de forma consistente no relatório (Task 1) e na CLI (Task 3).
