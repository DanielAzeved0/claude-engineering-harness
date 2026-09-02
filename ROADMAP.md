# ROADMAP.md

> Fases de desenvolvimento do Claude Engineering Harness. Regra de ouro: **não implemente uma fase futura inteira de uma vez** — cada fase segue o ciclo *implementar → compilar → testar → corrigir → validar → documentar* antes da próxima (princípio 8 em `PROJECT_CONTEXT.md`).

## Fase 1 — Core State Machine

**Status: ✅ COMPLETO**

- Persistência de estado (`.harness/state.json`)
- 12 estágios de workflow + 3 estados terminais
- Tabela de transições centralizada (`harness/transitions.py`)
- CLI: `harness init`, `harness status`, `harness start`, `harness transition`
- Criação automática da estrutura de diretórios `.harness/`

## Fase 2 — Agent Result Protocol

**Status: ✅ COMPLETO**

- Modelo estruturado de resultado de agente (`harness/models.py::AgentResult`)
- Validação de resultado (campos obrigatórios/opcionais, tipos, normalização de case)
- Processador de resultado (`harness/controller.py::process_result_file`)
- Transição automática a partir de um resultado validado (reaproveita `transitions.get_next_stage`, sem duplicar regras)
- CLI: `harness result PATH`
- Histórico de resultados em `state.history` (com timestamp, agente, artifacts, metadata)
- Testes automatizados (`tests/test_result_processing.py`, 15 testes no total na suíte)
- Primeiro workflow end-to-end dirigido por resultado de agente, validado tanto em teste automatizado (`tests/test_workflow.py`) quanto manualmente via CLI real (TASK → SPECIFICATION → PLANNING → EXECUTION → TESTING → DIAGNOSIS)

**Objetivo alcançado:** transições manuais (`harness transition`) deixaram de ser o único caminho — um agente já pode dirigir o workflow entregando um JSON estruturado.

## Fase 3 — Iteration Engine

**Status: ✅ COMPLETO**

- Funções puras de detecção de loop (`harness/iteration.py`): `increment_iteration`, `iteration_limit_exceeded`, `compute_root_cause_hash`, `register_root_cause`, `root_cause_repeated_too_often` (threshold = 3)
- `harness/controller.py::_apply_stage_transition` agora recebe o `state` completo; ao entrar em `DIAGNOSIS` (convergência de `TESTING FAIL` e `EXECUTION FAIL`), incrementa `state.iteration.current` e força `ESCALATED` se ultrapassar `state.iteration.max` (10)
- `process_result_file` registra a causa raiz (`metadata.root_cause`, com fallback pro `summary`) sempre que um resultado de `DIAGNOSIS` leva a `FIXING`; força `ESCALATED` se a mesma causa se repetir 3+ vezes
- Os dois guards nunca lançam exceção — reescrevem o resultado da transição antes de persistir, populando `state.escalation.reason`
- `start_task` reseta `state.escalation` (além de `iteration`/`loop_detection`), então uma tarefa nova nunca herda uma escalada de uma tarefa anterior
- Testes automatizados (`tests/test_iteration.py` + casos novos em `tests/test_result_processing.py`)

**Objetivo alcançado:** o ciclo `FIXING → EXECUTION → TESTING → DIAGNOSIS → FIXING` que antes podia rodar indefinidamente agora tem um teto real, e diagnósticos que reportam a mesma causa repetidamente escalam em vez de tentar de novo às cegas.

## Fase 4 — Artifact and Report System

**Status: ✅ COMPLETO**

- `harness/artifacts.py`: `artifact_exists_for_stage`, `list_artifact_status` (reaproveita `harness.roles.STAGE_ARTIFACT_KEY`, sem duplicar o mapeamento), `generate_execution_report` — função pura que compila `state.history` num relatório markdown mecânico
- `process_result_file` grava `artifact_present: bool` em cada entrada de histórico de resultado de agente
- Ao chegar em `COMPLETE` (por `harness transition` manual ou por resultado de agente), o Harness gera `.harness/reports/EXECUTION_REPORT.md` automaticamente — deliberadamente separado de `.harness/reports/FINAL_REPORT.md` (entregável narrativo do papel DOCUMENTER, nunca sobrescrito; verificado em revisão que só existem dois pontos de escrita em todo `harness/`: `state.json` e o relatório de execução)
- A escrita do relatório roda depois de `save_state()` (garante que o diretório existe e que o histórico já inclui a própria transição final) e nunca bloqueia a transição — falha de I/O só emite aviso
- CLI: `harness artifacts` — lista os 9 estágios com papel, caminho esperado e se existe no disco agora
- Validação é só informativa, não bloqueia nenhuma transição (o objetivo é rastreabilidade, não enforcement)
- Testes automatizados (`tests/test_artifacts.py`, `tests/test_cli_artifacts.py`, casos novos em `tests/test_result_processing.py`)

**Objetivo alcançado:** a qualquer momento dá pra saber quais artefatos esperados existem de verdade, e toda execução completa deixa um relatório mecânico e preciso — sem depender de nenhum agente lembrar de escrevê-lo.

## Fase 5 — Agent Role System

**Status: ✅ COMPLETO** (mapeamento e carregamento — invocação automática é a Fase 6)

- `harness/roles.py`: `STAGE_ROLE_MAP` (os 8 papéis carregados em código), `get_role_for_stage`, `get_role_template_path`, `load_role_prompt` (lê `roles/*.md` programaticamente), `build_agent_context` (contexto de agente: papel, artefato esperado, task id/title, resumo do último resultado, iteração atual)
- `ROLES_DIR` resolve relativo ao pacote (`Path(__file__).resolve().parent.parent / "roles"`), não ao cwd — funciona de qualquer diretório
- CLI: `harness role` — mostra estágio atual, papel responsável, caminho do template e artefato esperado; útil mesmo sem Runner, para um operador humano saber qual papel/prompt usar manualmente
- Testes automatizados (`tests/test_roles.py`, `tests/test_cli_role.py`)

**Objetivo alcançado:** o mapeamento estágio → papel e o carregamento de templates deixaram de ser só design documentado em `AGENTS.md` — são código de produção, consultável via `harness role`. O que ainda falta é a invocação automática de um agente de IA de verdade usando esse contexto (Fase 6, Claude Code Runner).

## Fase 6 — Claude Code Runner

**Status: ✅ COMPLETO**

- `harness/agents/base.py`: `AgentRunner` (ABC), `AgentRunOutcome`, `AgentRunError` — interface independente de qualquer agente específico
- `harness/agents/claude_code.py::ClaudeCodeRunner`: invoca o CLI `claude` via `subprocess` em modo não-interativo (`-p`, `--output-format json`, `--dangerously-skip-permissions`)
- `harness/controller.py::build_agent_prompt`: monta o prompt (template do papel + contexto + instruções explícitas do Agent Result Protocol), com um bloco de override no topo deixando claro que o agente nunca executa transições
- `harness/controller.py::run_current_stage`: orquestra a execução — invoca o runner, lê o resultado, sintetiza um `FAIL` automaticamente se o agente travar, sair sem escrever nada, ou escrever um resultado inutilizável
- CLI: `harness agent-run` (sem argumento de papel, deriva do estágio atual; `--timeout` opcional)
- Testes automatizados (`tests/test_agents_base.py`, `tests/test_claude_code_runner.py`, `tests/test_run_current_stage.py`, `tests/test_cli_agent_run.py`) — nenhum invoca um Claude Code de verdade

**Objetivo alcançado:** o Harness já invoca o Claude Code automaticamente — primeira vez que o Role System (Fase 5) e o Artifact System (Fase 4) são exercitados ponta a ponta, não só manualmente. Não existe loop autônomo entre estágios ainda (isso é a Fase 8) — um humano dispara `harness agent-run` manualmente, uma vez por estágio.

## Fase 7 — Quality Gates

**Status: ⬜ NÃO INICIADO** (schema já existe, avaliação não)

`state.quality_gates` já existe no schema (`build`, `lint`, `unit_tests`, `integration_tests`, `acceptance_tests`, `review`, cada um com `required`/`status`) e é exibido em `harness status`, mas nada os avalia ou os usa para bloquear uma transição para `COMPLETE`.

**Reordenada para depois do Runner** (era Fase 7 antes do Runner na numeração antiga, mas dependia dele de fato): só ganha valor pleno com sinais reais de build/lint/test vindos de agentes de verdade (Fase 6); antes disso, tudo é simulado via `Agent Result` manual.

Objetivo: impedir conclusão sem qualidade validada.

## Fase 8 — Autonomous Loop

**Status: ⬜ NÃO INICIADO**

Escopo planejado: comando `harness run`, execução automática de papel, processamento automático de resultado, transições automáticas, retries automáticos, loop teste/correção automático.

**Dependência:** orquestra Roles (Fase 5), Runner (Fase 6) e Quality Gates (Fase 7) — precisa das três para ter algo real para automatizar.

Objetivo: loop de engenharia totalmente autônomo.

## Fase 9 — Observability

**Status: ⚠️ PARCIAL** — escopo reduzido deliberadamente ao que tem fonte de dados real hoje

- CLI: `harness history` — timeline legível de `state.history`: transição, outcome, agente, resumo, timestamp e duração calculada entre entradas consecutivas
- Testes automatizados (`tests/test_cli_history.py`)

**Fora de escopo por enquanto:** métricas de tokens/custo, atividade de agente em tempo real, dashboards. Não têm fonte de dados até a Fase 6 (Runner) existir e produzir uso real. Se alguma dessas funcionalidades virar prioridade, deve ser escopada explicitamente como incremento desta fase.

## Fase 10 — Maestri ou integração de UI

**Status: ⬜ NÃO INICIADO**

Possíveis funcionalidades: visualização de workflow/agente, monitoramento de execução, navegação de artefatos, intervenção manual, gates de aprovação. A UI deve permanecer separada do controlador central (ver `PROJECT_CONTEXT.md`).

---

## Decisão: fonte da verdade de regras e schemas

`config/*.json` (`transitions.json`, `quality-gates.json`) e `schemas/*.json` (`agent-result`, `state`, `test-results`) existiam como arquivos vazios (0 bytes) desde a Fase 1, sem nenhum código Python que os lesse — enquanto `harness/transitions.py` e `harness/state.py::DEFAULT_STATE` já implementam essas mesmas regras em Python e funcionam. Removidos para eliminar uma segunda fonte da verdade ambígua e não referenciada (YAGNI). **Decisão:** Python (`transitions.py`, `models.py`, `state.py`) é a única fonte da verdade para regras de transição, validação de resultado e schema de estado. Se uma fase futura precisar de configuração externa de verdade (ex.: permitir customizar transições sem editar código), isso deve ser proposto e escopado explicitamente como parte daquela fase — não reintroduzido como arquivo vazio "para depois".

## CLI — implementado vs planejado

| Comando | Status |
|---|---|
| `harness init` | ✅ Implementado |
| `harness status` | ✅ Implementado |
| `harness start TASK-ID "Título"` | ✅ Implementado |
| `harness transition OUTCOME` | ✅ Implementado |
| `harness result PATH` | ✅ Implementado |
| `harness role` | ✅ Implementado (Fase 5) |
| `harness history` | ✅ Implementado (Fase 9, parcial) |
| `harness artifacts` | ✅ Implementado (Fase 4) |
| `harness run` | ⬜ Planejado (Fase 8) |
| `harness resume` | ⬜ Planejado |
| `harness reset` | ⬜ Planejado |
| `harness doctor` | ⬜ Planejado |
| `harness agent-run` | ✅ Implementado (Fase 6) |
| `harness test` / `harness diagnose` / `harness document` / `harness config` | ⬜ Planejado |

## Próximo passo recomendado

**Fase 4 (Artifact System), Fase 5 (Role System) e Fase 6 (Runner) já se conectam ponta a ponta** — `harness agent-run` invoca o Claude Code, que agora sabe (via o prompt montado) qual artefato o Harness espera em cada estágio. A próxima fase recomendada é a **Fase 7 — Quality Gates**: hoje `state.quality_gates` existe no schema mas nada o avalia; com o Runner produzindo resultados reais, dá pra popular esses gates com sinais de verdade antes de avançar pra Fase 8 (Autonomous Loop), que depende das três fases anteriores (5, 6, 7) estarem prontas — e que também é onde os riscos identificados na revisão de segurança da Fase 6 (falha de infraestrutura confundida com falha de tarefa, injeção via contexto do prompt, detecção de adulteração de `state.json`) precisam estar resolvidos antes de remover o checkpoint humano por estágio.
