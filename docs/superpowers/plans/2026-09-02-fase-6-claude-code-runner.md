# Fase 6 — Claude Code Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que o Harness invoque o Claude Code automaticamente para executar o papel do estágio atual do workflow, capturando um resultado estruturado de volta — primeira vez que o Role System (Fase 5) é validado ponta a ponta em vez de só manualmente.

**Architecture:** Dois módulos novos em `harness/agents/` — uma interface abstrata (`base.py`, sem nada específico de Claude Code, honrando o princípio de "independência de agente" de `PROJECT_CONTEXT.md`) e uma implementação concreta (`claude_code.py`, invoca o CLI `claude` via `subprocess`) — mais uma função de orquestração nova em `harness/controller.py` (que já é o dono de "aplicar resultado/transição") e um comando CLI novo. Quatro tasks sequenciais (uma trilha só, sem sub-blocos paralelos): interface → implementação concreta → orquestração → CLI, cada uma consumindo a anterior.

**Tech Stack:** Python 3.10+, stdlib apenas (`subprocess`, `abc`, `dataclasses`, `unittest`, `unittest.mock`) — sem dependências novas.

**Spec:** (aprovada em chat durante o brainstorming; resumo fiel abaixo)

> `harness/agents/base.py`: `AgentRunOutcome` (dataclass: `completed`, `timed_out`, `exit_code`, `stdout`, `stderr`), `AgentRunner` (ABC com `run(prompt, timeout_seconds) -> AgentRunOutcome`), `AgentRunError` (exceção só para falha de invocação, nunca para falha da tarefa em si).
>
> `harness/agents/claude_code.py`: `ClaudeCodeRunner(AgentRunner)` invoca `subprocess.run(["claude", "-p", prompt, "--output-format", "json", "--dangerously-skip-permissions"], capture_output=True, text=True, timeout=timeout_seconds)`. `--dangerously-skip-permissions` é necessário porque uma sessão headless não tem como aprovar ações interativamente — decisão aprovada explicitamente (autonomia completa por padrão), já que o checkpoint de segurança desta fase é outro: um humano ainda dispara `harness agent-run` manualmente, uma vez por estágio, sem loop automático (isso é a Fase 8).
>
> `harness/controller.py`: `DEFAULT_AGENT_TIMEOUT_SECONDS = 1800`. `build_agent_prompt(context, role_prompt, result_path) -> str` — função pura, concatena o template do papel + contexto (`build_agent_context`) + instruções explícitas do Agent Result Protocol (schema exato, caminho exato, outcomes permitidos via `get_allowed_outcomes` reaproveitado — hoje nenhum `roles/*.md` menciona esse contrato, o Runner é quem injeta isso no prompt). `run_current_stage(runner, timeout_seconds=DEFAULT_AGENT_TIMEOUT_SECONDS) -> dict` — monta o prompt, chama `runner.run(...)`, checa se o arquivo de resultado esperado existe; se não (timeout ou agente que saiu sem escrever nada), sintetiza um resultado `FAIL` com o motivo no mesmo caminho. Em ambos os casos, processa via `process_result_file` (reaproveitado, zero duplicação de lógica de transição) — o workflow nunca fica travado esperando um resultado que não vai chegar.
>
> CLI: `harness agent-run` — sem argumento de papel (deriva do estágio atual do workflow, igual `harness role` já faz). Flag opcional `--timeout SECONDS`.
>
> Documentação: corrige só o que ficou factualmente errado por esta fase — `ARCHITECTURE.md` (tabela de status + seção "Camada 2 — Agent Runner") e uma frase em `PROJECT_CONTEXT.md` que afirma que não existe nenhum Agent Runner implementado.

## Global Constraints

- Testes rodam com `python -m unittest discover -s tests -v` (padrão do projeto, ver `ARCHITECTURE.md:183`).
- Depois de cada task, rodar `python -m compileall harness` sem erros.
- Testes que envolvem `.harness/state.json` isolam-se em `tempfile.mkdtemp()` + `os.chdir()` no `setUp`/`tearDown` (padrão de `tests/test_result_processing.py`).
- **Nenhum teste desta fase invoca o CLI `claude` de verdade.** `ClaudeCodeRunner` é testado com `subprocess.run` mockado (`unittest.mock.patch`); `run_current_stage` é testado com um `AgentRunner` fake (dublê de teste que implementa a ABC diretamente em Python, sem subprocess nenhum).
- Sem dependências novas: tudo com stdlib.
- `harness/agents/base.py` não importa nada de `harness/roles.py`, `harness/controller.py` ou qualquer coisa específica do domínio do Harness — é uma interface agente-agnóstica de verdade.
- `--dangerously-skip-permissions` é uma string literal usada em exatamente um lugar (`harness/agents/claude_code.py`) — não duplicar em nenhum outro arquivo.

---

### Task 1: `harness/agents/base.py` — interface abstrata do runner

**Files:**
- Create: `harness/agents/__init__.py`
- Create: `harness/agents/base.py`
- Test: `tests/test_agents_base.py`

**Interfaces:**
- Consumes: nada (módulo novo, sem dependências do resto do projeto)
- Produces: `AgentRunOutcome` (dataclass), `AgentRunner` (ABC), `AgentRunError` (exceção) — usados pela Task 2 (`claude_code.py`) e Task 3 (`controller.py`).

- [ ] **Step 1: Escrever os testes (falhando)**

Criar `harness/agents/__init__.py` (vazio, só docstring, pra virar pacote):

```python
"""
Agent runner implementations for the Claude Engineering Harness.
"""
```

Criar `tests/test_agents_base.py`:

```python
"""
Tests for harness.agents.base.
"""

import unittest

from harness.agents.base import AgentRunError, AgentRunOutcome, AgentRunner


class FakeRunner(AgentRunner):
    def run(self, prompt: str, timeout_seconds: int) -> AgentRunOutcome:
        return AgentRunOutcome(
            completed=True,
            timed_out=False,
            exit_code=0,
            stdout=f"ran: {prompt}",
            stderr="",
        )


class AgentRunnerTestCase(unittest.TestCase):
    def test_cannot_instantiate_abstract_base_directly(self):
        with self.assertRaises(TypeError):
            AgentRunner()

    def test_concrete_subclass_can_run(self):
        runner = FakeRunner()
        outcome = runner.run("hello", 30)

        self.assertTrue(outcome.completed)
        self.assertFalse(outcome.timed_out)
        self.assertEqual(outcome.exit_code, 0)
        self.assertIn("hello", outcome.stdout)


class AgentRunOutcomeTestCase(unittest.TestCase):
    def test_holds_all_fields(self):
        outcome = AgentRunOutcome(
            completed=False,
            timed_out=True,
            exit_code=None,
            stdout="partial output",
            stderr="",
        )

        self.assertFalse(outcome.completed)
        self.assertTrue(outcome.timed_out)
        self.assertIsNone(outcome.exit_code)
        self.assertEqual(outcome.stdout, "partial output")


class AgentRunErrorTestCase(unittest.TestCase):
    def test_is_an_exception(self):
        self.assertTrue(issubclass(AgentRunError, Exception))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `python -m unittest tests.test_agents_base -v`
Expected: FAIL / ERROR — `ModuleNotFoundError: No module named 'harness.agents'`

- [ ] **Step 3: Implementar `harness/agents/base.py`**

```python
"""
Abstract agent runner interface for the Claude Engineering Harness.

Kept independent of any specific coding agent (Claude Code, or a
future one) so the Harness controller never depends on one particular
implementation — see the "independência de agente" principle in
PROJECT_CONTEXT.md.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


class AgentRunError(Exception):
    """Raised when an agent cannot be invoked at all (e.g. binary missing)."""


@dataclass
class AgentRunOutcome:
    completed: bool
    timed_out: bool
    exit_code: int | None
    stdout: str
    stderr: str


class AgentRunner(ABC):
    @abstractmethod
    def run(self, prompt: str, timeout_seconds: int) -> AgentRunOutcome:
        """
        Invoke the underlying coding agent with `prompt` and wait up to
        `timeout_seconds`. Must never raise for the agent's own failure
        or timeout — report that via AgentRunOutcome instead. Only raise
        AgentRunError when the agent cannot be invoked at all.
        """
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `python -m unittest tests.test_agents_base -v`
Expected: PASS (4 testes)

- [ ] **Step 5: Compilar e commitar**

```bash
python -m compileall harness
git add harness/agents/__init__.py harness/agents/base.py tests/test_agents_base.py
git commit -m "feat: add AgentRunner abstract interface"
```

---

### Task 2: `harness/agents/claude_code.py` — runner concreto via subprocess

**Files:**
- Create: `harness/agents/claude_code.py`
- Test: `tests/test_claude_code_runner.py`

**Interfaces:**
- Consumes: `harness.agents.base.AgentRunner`, `.AgentRunOutcome`, `.AgentRunError` (Task 1)
- Produces: `ClaudeCodeRunner(AgentRunner)` — usado pela Task 4 (`cli.py`).

- [ ] **Step 1: Escrever os testes (falhando)**

Criar `tests/test_claude_code_runner.py`:

```python
"""
Tests for harness.agents.claude_code.ClaudeCodeRunner.

Every subprocess.run call is mocked — these tests never invoke a real
Claude Code CLI.
"""

import subprocess
import unittest
from unittest.mock import MagicMock, patch

from harness.agents.base import AgentRunError
from harness.agents.claude_code import ClaudeCodeRunner


class ClaudeCodeRunnerTestCase(unittest.TestCase):
    def setUp(self):
        self.runner = ClaudeCodeRunner()

    @patch("harness.agents.claude_code.subprocess.run")
    def test_successful_run_returns_completed_outcome(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="done", stderr="")

        outcome = self.runner.run("do the thing", 30)

        self.assertTrue(outcome.completed)
        self.assertFalse(outcome.timed_out)
        self.assertEqual(outcome.exit_code, 0)
        self.assertEqual(outcome.stdout, "done")

        args, kwargs = mock_run.call_args
        command = args[0]
        self.assertEqual(command[0], "claude")
        self.assertIn("-p", command)
        self.assertIn("do the thing", command)
        self.assertIn("--dangerously-skip-permissions", command)
        self.assertEqual(kwargs["timeout"], 30)

    @patch("harness.agents.claude_code.subprocess.run")
    def test_timeout_returns_timed_out_outcome(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd="claude", timeout=30, output="partial", stderr="err"
        )

        outcome = self.runner.run("do the thing", 30)

        self.assertFalse(outcome.completed)
        self.assertTrue(outcome.timed_out)
        self.assertIsNone(outcome.exit_code)
        self.assertEqual(outcome.stdout, "partial")

    @patch("harness.agents.claude_code.subprocess.run")
    def test_missing_binary_raises_agent_run_error(self, mock_run):
        mock_run.side_effect = FileNotFoundError("no such file")

        with self.assertRaises(AgentRunError):
            self.runner.run("do the thing", 30)

    def test_custom_command_name(self):
        runner = ClaudeCodeRunner(command="my-claude")

        with patch("harness.agents.claude_code.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            runner.run("x", 10)

            args, _ = mock_run.call_args
            self.assertEqual(args[0][0], "my-claude")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `python -m unittest tests.test_claude_code_runner -v`
Expected: FAIL / ERROR — `ModuleNotFoundError: No module named 'harness.agents.claude_code'`

- [ ] **Step 3: Implementar `harness/agents/claude_code.py`**

```python
"""
Claude Code CLI runner for the Claude Engineering Harness.
"""

import subprocess

from harness.agents.base import AgentRunError, AgentRunOutcome, AgentRunner


class ClaudeCodeRunner(AgentRunner):
    def __init__(self, command: str = "claude") -> None:
        self._command = command

    def run(self, prompt: str, timeout_seconds: int) -> AgentRunOutcome:
        try:
            completed = subprocess.run(
                [
                    self._command,
                    "-p",
                    prompt,
                    "--output-format",
                    "json",
                    "--dangerously-skip-permissions",
                ],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            return AgentRunOutcome(
                completed=False,
                timed_out=True,
                exit_code=None,
                stdout=error.stdout or "",
                stderr=error.stderr or "",
            )
        except FileNotFoundError as error:
            raise AgentRunError(
                f"Claude Code CLI ('{self._command}') not found."
            ) from error

        return AgentRunOutcome(
            completed=True,
            timed_out=False,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `python -m unittest tests.test_claude_code_runner -v`
Expected: PASS (4 testes)

- [ ] **Step 5: Compilar e commitar**

```bash
python -m compileall harness
git add harness/agents/claude_code.py tests/test_claude_code_runner.py
git commit -m "feat: add ClaudeCodeRunner (subprocess-based agent invocation)"
```

---

### Task 3: Orquestração em `harness/controller.py`

**Files:**
- Modify: `harness/controller.py:9-22` (imports), adicionar `DEFAULT_AGENT_TIMEOUT_SECONDS`, `build_agent_prompt`, `run_current_stage` (novo bloco, ver Step 3)
- Test: `tests/test_run_current_stage.py`

**Interfaces:**
- Consumes: `harness.agents.base.AgentRunner` (Task 1), `harness.roles.build_agent_context`, `harness.roles.load_role_prompt`, `harness.transitions.get_allowed_outcomes` (já existem)
- Produces: `build_agent_prompt(context, role_prompt, result_path) -> str`, `run_current_stage(runner, timeout_seconds=DEFAULT_AGENT_TIMEOUT_SECONDS) -> dict` — usados pela Task 4 (`cli.py`).

- [ ] **Step 1: Escrever os testes (falhando)**

Criar `tests/test_run_current_stage.py`:

```python
"""
Tests for harness.controller.build_agent_prompt and run_current_stage.

Uses fake AgentRunner implementations (test doubles) — no subprocess,
no real Claude Code invocation.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from harness.agents.base import AgentRunner, AgentRunOutcome
from harness.controller import build_agent_prompt, run_current_stage, start_task
from harness.state import initialize_state, load_state


class ResultWritingRunner(AgentRunner):
    """Fake runner that writes a valid result file, simulating a real agent."""

    def __init__(self, outcome_json):
        self._outcome_json = outcome_json

    def run(self, prompt, timeout_seconds):
        result_path = self._extract_result_path(prompt)
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(self._outcome_json), encoding="utf-8")
        return AgentRunOutcome(
            completed=True, timed_out=False, exit_code=0, stdout="", stderr=""
        )

    @staticmethod
    def _extract_result_path(prompt):
        for line in prompt.splitlines():
            if "this path:" in line:
                return Path(line.split("this path:", 1)[1].strip())
        raise AssertionError("prompt did not include a result path")


class TimeoutRunner(AgentRunner):
    def run(self, prompt, timeout_seconds):
        return AgentRunOutcome(
            completed=False, timed_out=True, exit_code=None, stdout="", stderr=""
        )


class SilentRunner(AgentRunner):
    """Simulates an agent that exits without ever writing a result file."""

    def run(self, prompt, timeout_seconds):
        return AgentRunOutcome(
            completed=True, timed_out=False, exit_code=0, stdout="no-op", stderr=""
        )


class BuildAgentPromptTestCase(unittest.TestCase):
    def test_prompt_includes_role_template_context_and_protocol(self):
        context = {
            "stage": "TESTING",
            "role": "TESTER",
            "artifact_path": ".harness/tests/TEST_RESULTS.json",
            "task_id": "T-1",
            "task_title": "Sample task",
            "iteration": 0,
            "last_result_summary": None,
        }
        result_path = Path(".harness/results/testing-2026-01-01.json")

        prompt = build_agent_prompt(context, "ROLE TEMPLATE TEXT", result_path)

        self.assertIn("ROLE TEMPLATE TEXT", prompt)
        self.assertIn("T-1", prompt)
        self.assertIn(str(result_path), prompt)
        self.assertIn("PASS", prompt)
        self.assertIn("FAIL", prompt)


class RunCurrentStageTestCase(unittest.TestCase):
    def setUp(self):
        self._original_cwd = os.getcwd()
        self._temp_dir = tempfile.mkdtemp(prefix="harness-test-")
        os.chdir(self._temp_dir)
        initialize_state()
        start_task("T-1", "Sample task")

    def tearDown(self):
        os.chdir(self._original_cwd)
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    def test_successful_agent_run_advances_workflow(self):
        runner = ResultWritingRunner(
            {
                "agent": "maestro",
                "stage": "TASK",
                "outcome": "SUCCESS",
                "summary": "Captured the task",
            }
        )

        result = run_current_stage(runner)

        self.assertEqual(result["to"], "SPECIFICATION")

        state = load_state()
        self.assertEqual(state["workflow"]["current_stage"], "SPECIFICATION")

    def test_timeout_synthesizes_fail_result(self):
        result = run_current_stage(TimeoutRunner(), timeout_seconds=5)

        self.assertEqual(result["outcome"], "FAIL")
        self.assertIn("timed out", result["summary"])

    def test_silent_agent_synthesizes_fail_result(self):
        result = run_current_stage(SilentRunner())

        self.assertEqual(result["outcome"], "FAIL")
        self.assertIn("exited without producing", result["summary"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `python -m unittest tests.test_run_current_stage -v`
Expected: FAIL / ERROR — `ImportError: cannot import name 'build_agent_prompt' from 'harness.controller'`

- [ ] **Step 3: Modificar `harness/controller.py`**

Adicionar aos imports existentes do topo (a linha `from harness.transitions import TERMINAL_STAGES, get_next_stage` vira):

```python
from harness.agents.base import AgentRunner
from harness.roles import build_agent_context, load_role_prompt
from harness.transitions import TERMINAL_STAGES, get_allowed_outcomes, get_next_stage
```

(adicionar a nova linha `from harness.agents.base import AgentRunner` e a linha `from harness.roles import ...` junto às outras importações do topo, mantendo ordem alfabética por módulo — `agents` antes de `artifacts`, `roles` depois de `models`/antes de `state`)

Adicionar `DEFAULT_AGENT_TIMEOUT_SECONDS`, `build_agent_prompt` e `run_current_stage` no final do arquivo (depois de `start_task`):

```python
DEFAULT_AGENT_TIMEOUT_SECONDS = 1800


def build_agent_prompt(context: dict, role_prompt: str, result_path: Path) -> str:
    allowed_outcomes = get_allowed_outcomes(context["stage"])

    return (
        f"{role_prompt}\n\n"
        "## Harness Context\n\n"
        f"- Task ID: {context['task_id']}\n"
        f"- Task Title: {context['task_title']}\n"
        f"- Stage: {context['stage']}\n"
        f"- Iteration: {context['iteration']}\n"
        f"- Last result summary: {context['last_result_summary']}\n\n"
        "## Harness Result Protocol\n\n"
        "When you finish this role's work, write a JSON file to exactly "
        f"this path: {result_path}\n\n"
        "The JSON must have this shape:\n\n"
        "{\n"
        '  "agent": "<your role, lowercase>",\n'
        f'  "stage": "{context["stage"]}",\n'
        f'  "outcome": "<one of: {", ".join(allowed_outcomes)}>",\n'
        '  "summary": "<one-line summary of what happened>",\n'
        '  "artifacts": ["<paths of files you created or modified>"],\n'
        '  "metadata": {}\n'
        "}\n\n"
        "You report the outcome. You do NOT choose or execute the next "
        "workflow stage — the Harness applies the transition "
        "deterministically based on what you report."
    )


def run_current_stage(
    runner: AgentRunner, timeout_seconds: int = DEFAULT_AGENT_TIMEOUT_SECONDS
) -> dict[str, Any]:
    state = load_state()
    context = build_agent_context(state)
    role_prompt = load_role_prompt(context["role"])

    result_path = Path(
        f".harness/results/{context['stage'].lower()}-"
        f"{now_iso().replace(':', '-')}.json"
    )

    prompt = build_agent_prompt(context, role_prompt, result_path)

    outcome = runner.run(prompt, timeout_seconds)

    if not result_path.is_file():
        if outcome.timed_out:
            reason = f"timed out after {timeout_seconds}s"
        else:
            reason = (
                "exited without producing a result file "
                f"(exit_code={outcome.exit_code})"
            )

        fallback = {
            "agent": context["role"].lower(),
            "stage": context["stage"],
            "outcome": "FAIL",
            "summary": f"Agent {reason}.",
            "metadata": {
                "stdout_tail": outcome.stdout[-2000:],
                "stderr_tail": outcome.stderr[-2000:],
            },
        }
        result_path.write_text(json.dumps(fallback), encoding="utf-8")

    return process_result_file(result_path)
```

(`.harness/results/` já existe — está na lista de diretórios criados por `ensure_harness_structure()` desde a Fase 1, chamada por `save_state()`/`initialize_state()` antes de qualquer transição ser possível — mesmo raciocínio já usado para `.harness/reports/` na Fase 4, sem `mkdir` redundante.)

- [ ] **Step 4: Rodar toda a suíte e confirmar que passa**

Run: `python -m unittest discover -s tests -v`
Expected: PASS — todos os testes, incluindo os pré-existentes e os novos desta task.

- [ ] **Step 5: Compilar e commitar**

```bash
python -m compileall harness
git add harness/controller.py tests/test_run_current_stage.py
git commit -m "feat: add agent prompt builder and run_current_stage orchestration"
```

---

### Task 4: CLI `harness agent-run` + documentação

**Files:**
- Modify: `harness/cli.py` (imports, nova função `command_agent_run`, novo subparser em `build_parser`)
- Modify: `ARCHITECTURE.md:12` (tabela de status), `ARCHITECTURE.md:130-141` (seção "Camada 2 — Agent Runner")
- Modify: `PROJECT_CONTEXT.md:33`
- Test: `tests/test_cli_agent_run.py`

**Interfaces:**
- Consumes: `harness.controller.run_current_stage`, `.DEFAULT_AGENT_TIMEOUT_SECONDS` (Task 3), `harness.agents.claude_code.ClaudeCodeRunner` (Task 2), `harness.agents.base.AgentRunError` (Task 1)
- Produces: `command_agent_run(args)` — não consumido por nenhuma outra task deste plano.

- [ ] **Step 1: Escrever os testes (falhando)**

Criar `tests/test_cli_agent_run.py`:

```python
"""
Tests for the `harness agent-run` CLI command.

Mocks run_current_stage directly — this only tests the CLI wiring
(argument parsing, output formatting, error handling), not the
orchestration logic itself (covered by tests/test_run_current_stage.py)
or ClaudeCodeRunner (covered by tests/test_claude_code_runner.py).
"""

import argparse
import os
import shutil
import tempfile
import unittest
from io import StringIO
from unittest.mock import patch

from harness.cli import command_agent_run
from harness.state import initialize_state


class AgentRunCommandTestCase(unittest.TestCase):
    def setUp(self):
        self._original_cwd = os.getcwd()
        self._temp_dir = tempfile.mkdtemp(prefix="harness-test-")
        os.chdir(self._temp_dir)
        initialize_state()

    def tearDown(self):
        os.chdir(self._original_cwd)
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    @patch("harness.cli.run_current_stage")
    def test_agent_run_prints_result(self, mock_run_current_stage):
        mock_run_current_stage.return_value = {
            "agent": "maestro",
            "from": "TASK",
            "outcome": "SUCCESS",
            "to": "SPECIFICATION",
            "status": "RUNNING",
            "summary": "Captured the task",
        }

        args = argparse.Namespace(timeout=None)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            command_agent_run(args)

        output = mock_stdout.getvalue()
        self.assertIn("SPECIFICATION", output)
        mock_run_current_stage.assert_called_once()

    @patch("harness.cli.run_current_stage")
    def test_agent_run_uses_custom_timeout(self, mock_run_current_stage):
        mock_run_current_stage.return_value = {
            "agent": "maestro",
            "from": "TASK",
            "outcome": "SUCCESS",
            "to": "SPECIFICATION",
            "status": "RUNNING",
            "summary": "x",
        }

        args = argparse.Namespace(timeout=60)

        with patch("sys.stdout", new_callable=StringIO):
            command_agent_run(args)

        _, kwargs = mock_run_current_stage.call_args
        self.assertEqual(kwargs["timeout_seconds"], 60)

    @patch("harness.cli.run_current_stage")
    def test_agent_run_handles_error(self, mock_run_current_stage):
        mock_run_current_stage.side_effect = ValueError(
            "No active workflow stage."
        )

        args = argparse.Namespace(timeout=None)

        with patch("sys.stdout", new_callable=StringIO):
            with self.assertRaises(SystemExit):
                command_agent_run(args)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `python -m unittest tests.test_cli_agent_run -v`
Expected: FAIL — `ImportError: cannot import name 'command_agent_run' from 'harness.cli'`

- [ ] **Step 3: Implementar em `harness/cli.py`**

Trocar os imports do topo (linhas 9-13) por:

```python
from harness.agents.base import AgentRunError
from harness.agents.claude_code import ClaudeCodeRunner
from harness.artifacts import list_artifact_status
from harness.controller import (
    DEFAULT_AGENT_TIMEOUT_SECONDS,
    process_result_file,
    run_current_stage,
    start_task,
    transition,
)
from harness.roles import build_agent_context, get_role_template_path
from harness.state import initialize_state, load_state
from harness.transitions import get_allowed_outcomes
```

Adicionar nova função, logo após `command_artifacts` (antes de `def command_init`):

```python
def command_agent_run(args: argparse.Namespace) -> None:
    timeout = args.timeout if args.timeout else DEFAULT_AGENT_TIMEOUT_SECONDS

    try:
        result = run_current_stage(ClaudeCodeRunner(), timeout_seconds=timeout)
    except (FileNotFoundError, ValueError, AgentRunError) as error:
        print(f"Error: {error}")
        sys.exit(1)

    print()
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
```

Adicionar o subparser em `build_parser()`, logo antes de `return parser`:

```python
    agent_run_parser = subparsers.add_parser(
        "agent-run",
        help="Invoke Claude Code automatically for the current stage's role",
    )
    agent_run_parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help=f"Timeout in seconds (default: {DEFAULT_AGENT_TIMEOUT_SECONDS})",
    )
    agent_run_parser.set_defaults(func=command_agent_run)
```

- [ ] **Step 4: Corrigir `ARCHITECTURE.md`**

Trocar a linha 12 (tabela de status):

```
| **2. Agent Runner** | Executar o agente de IA (construir prompt, invocar Claude Code, capturar resultado) | ❌ **Não implementado** `[PLANEJADO — Fase 5]` |
```

por:

```
| **2. Agent Runner** | Executar o agente de IA (construir prompt, invocar Claude Code, capturar resultado) | ✅ **Implementado** |
```

Trocar a seção inteira (linhas 130-141, de `## Camada 2 — Agent Runner` até o parágrafo final dessa seção):

```
## Camada 2 — Agent Runner `[PLANEJADO — não implementado]`

Estrutura-alvo (nenhum destes arquivos existe hoje):

```text
harness/
├── agents/
│   ├── base.py
│   └── claude_code.py
```

Responsabilidade prevista: construir prompt, fornecer contexto do projeto, invocar Claude Code, aguardar execução, capturar saída/artefatos, produzir um arquivo de resultado estruturado (o mesmo formato validado por `harness/models.py`) e devolver o controle ao Harness. O runner **não decide transições** — apenas executa o papel solicitado.
```

por:

```
## Camada 2 — Agent Runner `[IMPLEMENTADO]`

```text
harness/
├── agents/
│   ├── __init__.py
│   ├── base.py
│   └── claude_code.py
```

`harness/agents/base.py` define `AgentRunner` (ABC) e `AgentRunOutcome` — interface intencionalmente independente de qualquer agente específico (princípio "independência de agente", ver acima). `harness/agents/claude_code.py::ClaudeCodeRunner` é a primeira implementação: invoca o CLI `claude` via `subprocess` em modo não-interativo (`-p`, `--output-format json`, `--dangerously-skip-permissions` — necessário porque uma sessão headless não tem como aprovar ações interativamente).

`harness/controller.py::build_agent_prompt` monta o prompt (template do papel + contexto + instruções explícitas do Agent Result Protocol) e `run_current_stage(runner)` orquestra: monta o prompt, invoca `runner.run(...)`, lê o arquivo de resultado que o agente deveria ter escrito, e processa via `process_result_file` (reaproveitado, sem duplicar lógica de transição). Se o agente travar, estourar timeout, ou nunca escrever o resultado esperado, `run_current_stage` sintetiza um resultado `FAIL` automaticamente — o workflow nunca fica travado esperando algo que não vai chegar. O runner **não decide transições** — apenas executa o papel solicitado.

CLI: `harness agent-run` (sem loop automático — um humano dispara uma vez por estágio; o loop autônomo é a Fase 8).
```

- [ ] **Step 5: Corrigir `PROJECT_CONTEXT.md`**

Trocar a linha 33:

```
O controlador deve, no entanto, ser **independente de agente** — a arquitetura separa `HARNESS CONTROLLER` de `AGENT RUNNER` para permitir trocar a implementação do agente no futuro. **Hoje não existe nenhum `AGENT RUNNER` implementado** (nenhuma invocação automática de Claude Code ou de qualquer outro agente); veja `ARCHITECTURE.md`.
```

por:

```
O controlador deve, no entanto, ser **independente de agente** — a arquitetura separa `HARNESS CONTROLLER` de `AGENT RUNNER` para permitir trocar a implementação do agente no futuro. O `AGENT RUNNER` já está implementado (`harness/agents/`, comando `harness agent-run`) com uma interface abstrata (`AgentRunner`) e uma primeira implementação concreta (`ClaudeCodeRunner`); veja `ARCHITECTURE.md`.
```

- [ ] **Step 6: Rodar os testes e confirmar que passam**

Run: `python -m unittest tests.test_cli_agent_run -v`
Expected: PASS (3 testes)

- [ ] **Step 7: Rodar toda a suíte, compilar e commitar**

```bash
python -m unittest discover -s tests -v
python -m compileall harness
git add harness/cli.py tests/test_cli_agent_run.py ARCHITECTURE.md PROJECT_CONTEXT.md
git commit -m "feat: add harness agent-run CLI command"
```

---

## Self-Review (feito ao escrever este plano)

**Cobertura da spec:**
- `AgentRunOutcome`/`AgentRunner`/`AgentRunError` ✅ Task 1.
- `ClaudeCodeRunner` via `subprocess`, com `--dangerously-skip-permissions` ✅ Task 2.
- `build_agent_prompt` (schema exato, `get_allowed_outcomes` reaproveitado) ✅ Task 3. `run_current_stage` (sucesso, timeout sintetiza FAIL, agente silencioso sintetiza FAIL, reaproveita `process_result_file`) ✅ Task 3.
- CLI `harness agent-run` sem argumento de papel, `--timeout` opcional ✅ Task 4.
- Documentação (`ARCHITECTURE.md`, `PROJECT_CONTEXT.md`) restrita ao que esta fase tornou factualmente errado ✅ Task 4.
- Nenhum teste invoca o CLI `claude` de verdade ✅ (Task 2 mocka `subprocess.run`; Task 3 usa `AgentRunner` fake; Task 4 mocka `run_current_stage`).

**Placeholders:** nenhum "TBD"/"implementar depois" — todo step tem código completo.

**Consistência de tipos:** `AgentRunner.run(prompt: str, timeout_seconds: int) -> AgentRunOutcome` implementado de forma idêntica em `ClaudeCodeRunner` (Task 2) e nos dublês de teste da Task 3/4. `run_current_stage(runner: AgentRunner, timeout_seconds=...) -> dict` — mesma assinatura usada em `command_agent_run` (Task 4) e nos testes (Task 3).
