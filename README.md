# Claude Engineering Harness

Controlador de workflow de engenharia determinístico para orquestrar agentes de IA de codificação (Claude Code), com máquina de estados, protocolo estruturado de resultado de agente, detecção de loop, sistema de artefatos/relatórios, papéis de agente e execução automática via CLI.

**Status resumido:** Fases 1 a 6 e Fase 9 (parcial) concluídas — máquina de estados, Agent Result Protocol, detecção de loop/escalonamento, sistema de artefatos e relatórios, papéis de agente (mapeamento + templates) e invocação automática do Claude Code (`harness agent-run`) já são código de produção, com 84 testes automatizados passando | Fase 7 (Quality Gates) e Fase 8 (Autonomous Loop) ainda não iniciadas — hoje um humano dispara cada estágio manualmente, um de cada vez | Fase 10 (integração de UI/Maestri) não iniciada. Progresso detalhado por fase está em [ROADMAP.md](ROADMAP.md); a visão de produto e os princípios de engenharia estão em [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md); os papéis de agente estão em [AGENTS.md](AGENTS.md).

## Índice

- [Sobre o Projeto](#sobre-o-projeto)
- [Objetivo](#objetivo)
- [Arquitetura](#arquitetura)
- [Fluxo do Sistema](#fluxo-do-sistema)
- [Funcionalidades](#funcionalidades)
- [Stack](#stack)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Princípios de Engenharia](#princípios-de-engenharia)
- [Como Executar](#como-executar)
- [Documentação](#documentação)
- [Roadmap](#roadmap)
- [Autor](#autor)

## Sobre o Projeto

O Claude Engineering Harness é um **controlador de workflow de engenharia autônomo**, projetado para orquestrar agentes de IA de codificação. O objetivo não é simplesmente pedir a uma IA que escreva código — é criar um **loop de engenharia controlado e repetível**, onde cada etapa (especificar, planejar, executar, testar, revisar, documentar) é delegada a um papel de agente especializado, mas as transições entre etapas continuam sendo decididas de forma determinística pelo Harness, nunca por inferência do agente.

A visão completa do produto — ideia central, objetivo de longo prazo, agente de codificação principal e não-objetivos — está em [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md).

## Objetivo

Permitir que um usuário forneça um pedido de alto nível de engenharia e o Harness coordene todo o processo — do estágio `TASK` ao `COMPLETE` — mantendo um controlador determinístico como autoridade sobre o que pode acontecer em seguida, enquanto a IA decide apenas *como* executar cada etapa.

**Status atual:** a invocação automática de um agente por estágio já existe (`harness agent-run`), mas a orquestração de ponta a ponta ainda não — não há loop autônomo entre `TASK` e `COMPLETE` (Fase 8, ver [ROADMAP.md](ROADMAP.md)).

## Arquitetura

```text
Humano/script
      ↓
harness agent-run (dispara um estágio)
      ↓
Agent Runner ──invoca──→ Claude Code (CLI, subprocess)
      ↓                         ↓
Agent Result Protocol  ←── resultado estruturado (JSON)
      ↓
Harness Controller (valida + decide a próxima transição)
      ↓
.harness/state.json (fonte única de verdade do estado)
```

| Camada | Responsabilidade | Status |
|---|---|---|
| **1. Harness Controller** | Máquina de estados, validação de resultado, transições, detecção de loop | Implementada |
| **2. Agent Runner** | Monta o prompt do papel, invoca o Claude Code, captura e valida o resultado | Implementada |
| **3. Agent Roles** | 8 papéis lógicos (Maestro, Spec Engineer, Planner, Executor, Tester, Debugger, Reviewer, Documenter) mapeados por estágio | Implementada |

Nenhum componente decide transições fora de `harness/transitions.py` — é a fonte única de verdade das regras de workflow. Detalhes de cada módulo estão em [ARCHITECTURE.md](ARCHITECTURE.md).

## Fluxo do Sistema

```text
TASK → SPECIFICATION → PLANNING → EXECUTION → TESTING → PASS?
                                                            ├── YES → REVIEW → DOCUMENTATION → COMPLETE
                                                            └── NO  → DIAGNOSIS → FIXING → EXECUTION → TESTING → ↺
```

1. Um humano inicia uma tarefa (`harness start TASK-ID "Título"`).
2. Para o estágio atual, o Harness resolve o papel responsável e monta o prompt (papel + contexto + instruções do Agent Result Protocol).
3. `harness agent-run` invoca o Claude Code, que executa o trabalho e escreve um resultado estruturado (JSON).
4. O Harness valida o resultado e aplica a transição correspondente da tabela `harness/transitions.py`.
5. O ciclo `DIAGNOSIS → FIXING → EXECUTION → TESTING` se repete até sucesso, até o limite de iterações (10) ou até a mesma causa raiz se repetir 3+ vezes — nesses casos o workflow escala automaticamente (`ESCALATED`) em vez de tentar de novo às cegas.
6. Ao chegar em `COMPLETE`, o Harness gera `.harness/reports/EXECUTION_REPORT.md` automaticamente a partir do histórico.

## Funcionalidades

### Implementadas

- Máquina de estados com 12 estágios de workflow + 3 estados terminais (`COMPLETE`, `BLOCKED`, `ESCALATED`), persistida em `.harness/state.json`
- Agent Result Protocol: validação estrutural de resultado de agente, com transição automática a partir de um resultado válido
- Detecção de loop: teto de iterações (10) e escalonamento por causa raiz repetida (3+ vezes)
- Sistema de artefatos e relatórios: `harness artifacts` lista o que cada estágio espera e se existe no disco; `.harness/reports/EXECUTION_REPORT.md` é gerado automaticamente ao concluir
- Papéis de agente: mapeamento estágio → papel, carregamento de templates (`roles/*.md`), consultável via `harness role`
- Runner do Claude Code: `harness agent-run` invoca o CLI `claude` automaticamente para o papel do estágio atual, sintetizando um resultado `FAIL` se o agente travar, estourar timeout ou não escrever o resultado esperado
- Observabilidade parcial: `harness history` exibe a timeline legível de transições, outcomes, papéis e duração entre eventos

### Planejadas

- Quality Gates (Fase 7): avaliar sinais reais de build/lint/test antes de permitir `COMPLETE`
- Autonomous Loop (Fase 8): `harness run` — execução e transição automáticas entre todos os estágios, sem disparo manual por etapa
- Integração de UI/Maestri (Fase 10): visualização de workflow, monitoramento de execução, gates de aprovação manual

## Stack

Python 3.10+, biblioteca padrão apenas no núcleo do Harness (`argparse`, `json`, `dataclasses`, `pathlib`, `datetime`, `subprocess`) — sem dependências de runtime externas. Empacotamento via `setuptools` (`pyproject.toml`), ponto de entrada `harness = "harness.cli:main"`. Testes com `unittest` (biblioteca padrão). Agente de codificação invocado: [Claude Code](https://claude.com/claude-code) CLI, tratado como implementação substituível de `AgentRunner` — o núcleo não depende exclusivamente dele.

## Estrutura do Projeto

```text
claude-engineering-harness/
├── README.md
├── ARCHITECTURE.md          # arquitetura atual, módulo a módulo
├── PROJECT_CONTEXT.md       # visão de produto e princípios de engenharia
├── ROADMAP.md               # fases de desenvolvimento e status
├── AGENTS.md                # papéis de agente e Agent Result Protocol
├── pyproject.toml
├── harness/
│   ├── cli.py                # interface de linha de comando (argparse)
│   ├── controller.py         # orquestração de transições, prompt e execução de estágio
│   ├── models.py             # AgentResult + validação
│   ├── state.py               # persistência de .harness/state.json
│   ├── transitions.py         # tabela de transições — fonte única de verdade
│   ├── iteration.py           # detecção de loop e limite de iterações
│   ├── artifacts.py           # status de artefatos e relatório de execução
│   ├── roles.py               # mapeamento estágio → papel, carregamento de templates
│   └── agents/
│       ├── base.py            # interface AgentRunner (independente de agente)
│       └── claude_code.py     # ClaudeCodeRunner (subprocess)
├── roles/                    # 8 templates de prompt (Markdown)
├── tests/                    # suíte unittest (84 testes)
└── docs/superpowers/plans/   # planos de implementação por fase
```

## Princípios de Engenharia

O Harness aplica princípios obrigatórios para qualquer mudança futura:

1. **Controle determinístico** — transições de workflow nunca são decididas por inferência de um agente.
2. **Independência de agente** — o núcleo não deve depender exclusivamente do Claude Code.
3. **Artefatos em vez de memória** — informação importante do workflow é persistida em disco (`.harness/`).
4. **Validar antes de transicionar** — nunca transicionar com base em resposta de agente não validada.
5. **Sem loops infinitos** — todo mecanismo de retry eventualmente termina ou escala.
6. **Falhar com segurança** — resultados malformados nunca corrompem o estado.
7. **Fonte única de verdade** — regras de transição centralizadas em `harness/transitions.py`.
8. **Desenvolvimento incremental** — cada fase é implementada, testada e documentada antes da próxima.
9. **Testar o próprio Harness** — toda funcionalidade importante do controlador tem testes automatizados.

Detalhamento completo em [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md).

## Como Executar

```bash
git clone <repo-url>
cd claude-engineering-harness
pip install -e .
```

Fluxo básico:

```bash
harness init                              # cria .harness/ e state.json
harness start TASK-001 "Minha tarefa"     # inicia o workflow no estágio TASK
harness status                            # mostra estágio, iteração, outcomes permitidos
harness role                              # mostra o papel responsável pelo estágio atual
harness agent-run                         # invoca o Claude Code para o estágio atual
harness history                           # timeline do workflow
harness artifacts                         # artefatos esperados vs existentes no disco
```

Alternativa manual (sem invocar o Claude Code): produza um JSON de resultado seguindo o Agent Result Protocol (ver [AGENTS.md](AGENTS.md)) e rode `harness result <path>`.

Rodar a suíte de testes:

```bash
python -m unittest discover -s tests -v
```

## Documentação

| Arquivo | Função |
|---|---|
| [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) | Visão de produto, princípios de engenharia e não-objetivos |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Arquitetura atual, módulo a módulo, incluindo o que ainda não existe |
| [ROADMAP.md](ROADMAP.md) | Fases de desenvolvimento, status detalhado e decisões de arquitetura |
| [AGENTS.md](AGENTS.md) | Papéis de agente, Agent Result Protocol e mapeamento estágio → papel |
| `docs/superpowers/plans/` | Planos de implementação registrados por fase |

## Roadmap

Visão resumida por fase. Detalhes e critérios de conclusão de cada fase estão em [ROADMAP.md](ROADMAP.md) (backlog e fonte de verdade sobre progresso).

| Fase | Tema | Status |
|---|---|---|
| 1 | Core State Machine | Concluída |
| 2 | Agent Result Protocol | Concluída |
| 3 | Iteration Engine (detecção de loop e escalonamento) | Concluída |
| 4 | Artifact and Report System | Concluída |
| 5 | Agent Role System (mapeamento e templates) | Concluída |
| 6 | Claude Code Runner (invocação automática) | Concluída |
| 7 | Quality Gates | Não iniciada |
| 8 | Autonomous Loop | Não iniciada |
| 9 | Observability | Parcial — `harness history` implementado; métricas de tokens/custo fora de escopo por enquanto |
| 10 | Integração de UI/Maestri | Não iniciada |

## Autor

Desenvolvido por Daniel Azevedo como projeto de engenharia para explorar orquestração determinística de agentes de IA de codificação.
