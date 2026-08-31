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

**Status: ⬜ NÃO INICIADO** (próxima fase recomendada)

Escopo planejado:

- Incrementar `state.iteration.current` a cada ciclo EXECUTION→TESTING→DIAGNOSIS→FIXING
- Aplicar `state.iteration.max` como limite de tentativas
- Rastreamento de causa raiz (`state.loop_detection.last_root_cause_hash`)
- Detecção de falha repetida (`state.loop_detection.same_root_cause_count`)
- Escalonamento automático para `ESCALATED` quando o limite ou o threshold de repetição forem atingidos

**Nota de implementação:** os campos `iteration` e `loop_detection` **já existem no schema de estado** (`harness/state.py::DEFAULT_STATE`) e já são exibidos por `harness status`, mas nenhuma lógica os popula além do reset em `start_task`. Esta fase é sobre *usar* esses campos, não criá-los.

Objetivo: impedir loops de IA infinitos.

## Fase 4 — Agent Role System

**Status: ⚠️ SCAFFOLDING PARCIAL — lógica não iniciada**

Escopo planejado:

- Definições de papel carregadas em código (Maestro, Spec Engineer, Planner, Executor, Tester, Debugger, Reviewer, Documenter)
- Templates de prompt por papel
- Mapeamento estágio → papel responsável
- Requisitos de artefato por papel
- Contexto de agente (o que cada papel recebe como entrada)

**Nota de implementação:** os 8 templates de prompt em Markdown **já existem** em `roles/*.md` (conteúdo completo, escrito), mas **nenhum código Python os carrega, referencia ou usa** hoje. Esta fase conecta esses templates ao controlador.

Objetivo: tornar o workflow dirigido por papel.

## Fase 5 — Claude Code Runner

**Status: ⬜ NÃO INICIADO**

Escopo planejado: invocação do Claude Code, geração de prompt, monitoramento de execução, coleta de saída, geração de resultado estruturado (compatível com `harness/models.py::AgentResult`), tratamento de erro e timeout. Estrutura-alvo: `harness/agents/base.py`, `harness/agents/claude_code.py`.

Objetivo: permitir que o Harness invoque o Claude Code automaticamente.

## Fase 6 — Autonomous Loop

**Status: ⬜ NÃO INICIADO**

Escopo planejado: comando `harness run`, execução automática de papel, processamento automático de resultado, transições automáticas, retries automáticos, loop teste/correção automático.

Objetivo: loop de engenharia totalmente autônomo.

## Fase 7 — Quality Gates

**Status: ⬜ NÃO INICIADO** (schema já existe, avaliação não)

`state.quality_gates` já existe no schema (`build`, `lint`, `unit_tests`, `integration_tests`, `acceptance_tests`, `review`, cada um com `required`/`status`) e é exibido em `harness status`, mas nada os avalia ou os usa para bloquear uma transição para `COMPLETE`.

Objetivo: impedir conclusão sem qualidade validada.

## Fase 8 — Artifact and Report System

**Status: ⬜ NÃO INICIADO**

`state.artifacts` já mapeia caminhos esperados (`TASK.md`, `SPEC.md`, `PLAN.md`, etc.) e os diretórios `.harness/*/` já são criados automaticamente, mas nenhum código ainda escreve esses arquivos.

Objetivo: rastreabilidade completa de engenharia.

## Fase 9 — Observability

**Status: ⬜ NÃO INICIADO**

Possíveis funcionalidades: visualização de workflow, timeline, atividade de agente, histórico de iteração, falhas, métricas, duração, uso de tokens, estimativa de custo.

## Fase 10 — Maestri ou integração de UI

**Status: ⬜ NÃO INICIADO**

Possíveis funcionalidades: visualização de workflow/agente, monitoramento de execução, navegação de artefatos, intervenção manual, gates de aprovação. A UI deve permanecer separada do controlador central (ver `PROJECT_CONTEXT.md`).

---

## CLI — implementado vs planejado

| Comando | Status |
|---|---|
| `harness init` | ✅ Implementado |
| `harness status` | ✅ Implementado |
| `harness start TASK-ID "Título"` | ✅ Implementado |
| `harness transition OUTCOME` | ✅ Implementado |
| `harness result PATH` | ✅ Implementado |
| `harness run` | ⬜ Planejado (Fase 6) |
| `harness resume` | ⬜ Planejado |
| `harness reset` | ⬜ Planejado |
| `harness history` | ⬜ Planejado |
| `harness artifacts` | ⬜ Planejado |
| `harness doctor` | ⬜ Planejado |
| `harness agent run ROLE` | ⬜ Planejado (Fase 4/5) |
| `harness test` / `harness diagnose` / `harness document` / `harness config` | ⬜ Planejado |

## Próximo passo recomendado

**Fase 3 — Iteration Engine.** É a lacuna mais próxima do núcleo determinístico já implementado (não depende de invocar um agente de IA de verdade, apenas de lógica de controle sobre o estado existente), e é um pré-requisito de segurança (princípio "Sem loops infinitos") antes de avançar para papéis de agente (Fase 4) ou execução autônoma (Fase 5/6).
