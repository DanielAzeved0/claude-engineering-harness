# ARCHITECTURE.md

> Descreve a arquitetura **atual** do Claude Engineering Harness. Para a visão de longo prazo e o que ainda não existe, veja `PROJECT_CONTEXT.md` e `ROADMAP.md`. Seções marcadas `[PLANEJADO]` descrevem a arquitetura-alvo das camadas ainda não implementadas — nenhum código correspondente existe hoje.

## Camadas conceituais

O projeto foi desenhado em torno de três camadas:

| Camada | Responsabilidade | Status |
|---|---|---|
| **1. Harness Controller** | Controle determinístico de workflow (estado, transições, validação) | ✅ **Implementado** |
| **2. Agent Runner** | Executar o agente de IA (construir prompt, invocar Claude Code, capturar resultado) | ❌ **Não implementado** `[PLANEJADO — Fase 5]` |
| **3. Agent Roles** | Papéis lógicos (Maestro, Spec Engineer, Planner, Executor, Tester, Debugger, Reviewer, Documenter) | ⚠️ **Parcial** — apenas templates de prompt estáticos em `roles/*.md`; nenhum código os carrega ou invoca `[PLANEJADO — Fase 4]` |

Hoje, o repositório implementa **apenas a Camada 1**. Um agente externo (humano ou script) produz manualmente os arquivos de resultado que a Camada 1 consome via `harness result`.

---

## Camada 1 — Harness Controller (implementada)

### Módulos

```text
harness/
├── __init__.py       # metadata do pacote (__version__)
├── cli.py             # interface de linha de comando (argparse)
├── controller.py      # orquestração de transições e processamento de resultados
├── models.py          # modelo de dados AgentResult + validação
├── state.py            # persistência de estado (.harness/state.json)
└── transitions.py      # tabela de transições — fonte única de verdade
```

Não existem dependências externas — apenas biblioteca padrão do Python (`argparse`, `json`, `dataclasses`, `pathlib`, `datetime`).

### `harness/transitions.py`

Fonte única de verdade para transições de estado. Contém:

- `TRANSITIONS: dict` — mapa `{estágio: {outcome: próximo_estágio}}`.
- `TERMINAL_STAGES: set` — `{"COMPLETE", "BLOCKED", "ESCALATED"}`.
- `get_next_stage(current_stage, outcome) -> str` — levanta `ValueError` para estágio terminal, estágio desconhecido ou outcome inválido.
- `get_allowed_outcomes(current_stage) -> list[str]`.

Nenhum outro módulo decide transições — `controller.py` sempre delega a `get_next_stage`.

### `harness/state.py`

- `DEFAULT_STATE` — schema completo do estado inicial (workflow, task, iteration, loop_detection, quality_gates, artifacts, last_result, escalation, history).
- `ensure_harness_structure()` — cria os diretórios de `.harness/` (idempotente).
- `initialize_state()` — cria `.harness/state.json`; levanta `FileExistsError` se já existir.
- `load_state()` / `save_state(state)` — leitura/escrita de `.harness/state.json` em UTF-8, JSON indentado. `save_state` sempre atualiza `workflow.updated_at`.

### `harness/models.py`

- `AgentResult` (dataclass): `agent`, `stage`, `outcome`, `summary` (obrigatórios), `artifacts: list`, `metadata: dict` (opcionais, default vazio).
- `parse_agent_result(data: dict) -> AgentResult` — valida um dict cru (tipicamente carregado de JSON): campos obrigatórios devem ser strings não vazias; `stage` e `outcome` são normalizados para uppercase; `artifacts` deve ser lista quando presente; `metadata` deve ser objeto quando presente. Levanta `ValueError` descritivo em qualquer violação.

### `harness/controller.py`

- `_apply_stage_transition(workflow, outcome) -> (previous_stage, next_stage)` — helper interno compartilhado. Chama `get_next_stage` (que pode levantar `ValueError`) **antes** de mutar o dict `workflow`, garantindo que uma transição rejeitada nunca deixe estado parcialmente alterado.
- `start_task(task_id, title) -> dict` — só permite iniciar se `workflow.status` estiver em `{IDLE, COMPLETE, FAILED, BLOCKED, ESCALATED}`; define estágio `TASK`, zera `iteration.current` e `loop_detection`, reseta `history`.
- `transition(outcome) -> dict` — transição manual (usada por `harness transition`). Usa `_apply_stage_transition`, adiciona entrada em `history` (`type: "manual"`), persiste.
- `process_result_file(path) -> dict` — **Protocolo de Resultado de Agente** (usado por `harness result`). Fluxo:
  1. Confirma que o arquivo existe (`FileNotFoundError`).
  2. Faz `json.load`; JSON inválido vira `ValueError` descritivo.
  3. Valida a estrutura via `parse_agent_result` (`ValueError`).
  4. Carrega `state.json`; confirma que há workflow ativo (`current_stage is not None`).
  5. Confirma que `result.stage == workflow.current_stage` — caso contrário rejeita (`ValueError`).
  6. Calcula a transição via `_apply_stage_transition` (que também rejeita estágio terminal ou outcome inválido para o estágio, via `get_next_stage`).
  7. Atualiza `state.last_result` (`agent`, `status`, `summary`).
  8. Anexa uma entrada rica em `state.history` (`type: "agent_result"`, agente, estágio anterior/novo, outcome, summary, artifacts, metadata, caminho do arquivo, timestamp UTC ISO 8601).
  9. Persiste via `save_state` — **só depois** que todas as validações acima passaram, garantindo que um resultado rejeitado nunca corrompe o estado.

### `harness/cli.py`

Interface via `argparse`, subcomando `prog="harness"`. Todo erro de domínio (`FileNotFoundError`, `ValueError`) é capturado no nível do comando, impresso como `Error: <mensagem>` e o processo sai com código 1.

| Comando | Função | Descrição |
|---|---|---|
| `harness init` | `command_init` | Cria `.harness/` e `state.json` |
| `harness status` | `command_status` | Exibe status, estágio, iteração, task, quality gates, outcomes permitidos |
| `harness start TASK-ID "Título"` | `command_start` | Inicia um novo workflow no estágio `TASK` |
| `harness transition OUTCOME` | `command_transition` | Transição manual |
| `harness result PATH` | `command_result` | Processa um arquivo de resultado de agente e transiciona automaticamente |

Ponto de entrada do pacote (`pyproject.toml`): `harness = "harness.cli:main"`.

### Persistência de estado — `.harness/state.json`

Schema atual (produzido por `DEFAULT_STATE`):

```json
{
  "harness_version": "0.1.0",
  "workflow": {
    "status": "IDLE | RUNNING | COMPLETE | BLOCKED | ESCALATED",
    "current_stage": null,
    "previous_stage": null,
    "started_at": null,
    "updated_at": null
  },
  "task": { "id": null, "title": null, "created_at": null },
  "iteration": { "current": 0, "max": 10 },
  "loop_detection": { "same_root_cause_count": 0, "last_root_cause_hash": null },
  "quality_gates": { "build": {"required": true, "status": "PENDING"}, "...": "..." },
  "artifacts": { "task": ".harness/task/TASK.md", "...": "..." },
  "last_result": { "agent": null, "status": null, "summary": null },
  "escalation": { "required": false, "reason": null },
  "history": []
}
```

**Importante:** `iteration` e `loop_detection` já existem no schema e são exibidos em `harness status`, mas **nenhuma lógica os incrementa ou avalia ainda** — `iteration.current` é sempre zerado em `start_task` e nunca mais tocado; não há detecção de loop. Isso é trabalho da Fase 3 (`ROADMAP.md`).

### Estrutura de diretórios `.harness/`

Criada automaticamente por `ensure_harness_structure()`:

```text
.harness/
├── state.json
├── task/ spec/ plan/ execution/ tests/ diagnosis/
├── review/ documentation/ results/ iterations/ reports/
```

Os subdiretórios são criados vazios; nenhum código ainda escreve artefatos Markdown/JSON neles automaticamente (isso é a Fase 8 — Artifact and Report System). A convenção de onde um agente deve salvar um resultado (`.harness/results/`) já é suportada por `harness result`, mas **qualquer caminho** de arquivo é aceito, dentro ou fora dessa pasta.

---

## Camada 2 — Agent Runner `[PLANEJADO — não implementado]`

Estrutura-alvo (nenhum destes arquivos existe hoje):

```text
harness/
├── agents/
│   ├── base.py
│   └── claude_code.py
```

Responsabilidade prevista: construir prompt, fornecer contexto do projeto, invocar Claude Code, aguardar execução, capturar saída/artefatos, produzir um arquivo de resultado estruturado (o mesmo formato validado por `harness/models.py`) e devolver o controle ao Harness. O runner **não decide transições** — apenas executa o papel solicitado.

## Camada 3 — Agent Roles `[PARCIAL — apenas templates estáticos]`

O diretório `roles/` já existe no repositório com 8 templates de prompt em Markdown (não vinculados a nenhum código Python ainda):

```text
roles/
├── maestro.md
├── spec-engineer.md
├── planner.md
├── executor.md
├── tester.md
├── debugger.md
├── reviewer.md
└── documenter.md
```

Esses arquivos descrevem o comportamento esperado de cada papel (ver `AGENTS.md`), mas **nada em `harness/` os lê, carrega ou usa** para construir prompts hoje — são artefatos de planejamento para a Fase 4 (Sistema de Papéis de Agente).

## Scaffolding adicional presente mas não conectado

Os diretórios abaixo existem no repositório mas **estão vazios ou desconectados do código-fonte**:

- `config/quality-gates.json` — 0 bytes (vazio)
- `config/transitions.json` — 0 bytes (vazio; a tabela de transições real e usada em produção está em `harness/transitions.py`, hardcoded em Python, não neste JSON)
- `schemas/agent-result.schema.json`, `schemas/state.schema.json`, `schemas/test-results.schema.json` — todos 0 bytes (vazios)

Nenhum desses arquivos é lido por `harness/*.py` atualmente. Antes de usá-los ou populá-los em uma tarefa futura, confirme com o usuário a intenção (ex.: migrar `TRANSITIONS` para `config/transitions.json`, ou usar os schemas para validação JSON Schema formal) — isso seria uma mudança de arquitetura, não uma correção trivial.

---

## Testes

```text
tests/
├── __init__.py
├── test_transitions.py         # tabela de transições pura (sem I/O)
├── test_result_processing.py   # process_result_file: sucesso e todos os casos de rejeição
└── test_workflow.py            # end-to-end: TASK → ... → DIAGNOSIS via resultados de agente
```

Executados com `python -m unittest discover -s tests -v`. Cada `TestCase` roda em um diretório temporário isolado (`tempfile.mkdtemp` + `os.chdir` no `setUp`/`tearDown`) — o `.harness/` real do desenvolvedor nunca é alterado pelos testes.

## Empacotamento

`pyproject.toml`: build via `setuptools`, `requires-python = ">=3.10"`, sem dependências de runtime. `[project.scripts] harness = "harness.cli:main"`. `[tool.setuptools] packages = ["harness"]` (lista explícita — `tests/`, `roles/`, `config/`, `schemas/` não são empacotados).
