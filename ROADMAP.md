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

**Status: ⬜ NÃO INICIADO**

`state.artifacts` já mapeia caminhos esperados (`TASK.md`, `SPEC.md`, `PLAN.md`, etc.) e os diretórios `.harness/*/` já são criados automaticamente, mas nenhum código ainda escreve esses arquivos.

**Reordenada para antes do Role System e do Runner** (era Fase 8): é de baixo risco e quase independente das demais fases — os paths já existem em `state["artifacts"]`, só falta escrever os arquivos — e desbloqueia rastreabilidade completa antes mesmo de existirem agentes reais.

Objetivo: rastreabilidade completa de engenharia.

## Fase 5 — Agent Role System

**Status: ✅ COMPLETO** (mapeamento e carregamento — invocação automática é a Fase 6)

- `harness/roles.py`: `STAGE_ROLE_MAP` (os 8 papéis carregados em código), `get_role_for_stage`, `get_role_template_path`, `load_role_prompt` (lê `roles/*.md` programaticamente), `build_agent_context` (contexto de agente: papel, artefato esperado, task id/title, resumo do último resultado, iteração atual)
- `ROLES_DIR` resolve relativo ao pacote (`Path(__file__).resolve().parent.parent / "roles"`), não ao cwd — funciona de qualquer diretório
- CLI: `harness role` — mostra estágio atual, papel responsável, caminho do template e artefato esperado; útil mesmo sem Runner, para um operador humano saber qual papel/prompt usar manualmente
- Testes automatizados (`tests/test_roles.py`, `tests/test_cli_role.py`)

**Objetivo alcançado:** o mapeamento estágio → papel e o carregamento de templates deixaram de ser só design documentado em `AGENTS.md` — são código de produção, consultável via `harness role`. O que ainda falta é a invocação automática de um agente de IA de verdade usando esse contexto (Fase 6, Claude Code Runner).

## Fase 6 — Claude Code Runner

**Status: ⬜ NÃO INICIADO**

Escopo planejado: invocação do Claude Code, geração de prompt, monitoramento de execução, coleta de saída, geração de resultado estruturado (compatível com `harness/models.py::AgentResult`), tratamento de erro e timeout. Estrutura-alvo: `harness/agents/base.py`, `harness/agents/claude_code.py`.

**Dependência:** consome o mapeamento estágio → papel da Fase 5 (`harness/roles.py::build_agent_context`), **já implementada**. Esta é a próxima fase que de fato valida o Role System ponta a ponta — hoje nenhum agente real é invocado, `build_agent_context` só é consumido manualmente via `harness role`.

Objetivo: permitir que o Harness invoque o Claude Code automaticamente.

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
| `harness run` | ⬜ Planejado (Fase 8) |
| `harness resume` | ⬜ Planejado |
| `harness reset` | ⬜ Planejado |
| `harness artifacts` | ⬜ Planejado (Fase 4) |
| `harness doctor` | ⬜ Planejado |
| `harness agent run ROLE` | ⬜ Planejado (Fase 6) |
| `harness test` / `harness diagnose` / `harness document` / `harness config` | ⬜ Planejado |

## Próximo passo recomendado

**Fase 4 — Artifact and Report System.** Fases 3, 5 e 9 (parcial) foram implementadas em paralelo (ver commits `e25e282`..`ab43be8` em `main`) fora da ordem estritamente sequencial deste roadmap — eram independentes o suficiente pra isso (ver mapa de arquivos tocados por cada uma, sem sobreposição real). A Fase 4 continua sendo a próxima recomendada: é de baixo risco, quase independente das demais, e desbloqueia rastreabilidade completa antes da Fase 6 (Claude Code Runner), que é a peça que realmente aumenta a superfície de risco do projeto (primeira vez que o Harness invoca algo externo automaticamente).
