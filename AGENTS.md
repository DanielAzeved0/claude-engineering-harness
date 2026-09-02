# AGENTS.md

> Descreve os papéis de agente (lógicos) do Claude Engineering Harness: suas responsabilidades, artefatos e limites. **Status atual: o mapeamento estágio → papel, o carregamento de templates, e a invocação automática do Claude Code já são código de produção** (`harness/roles.py` + `harness/agents/` + `harness/controller.py::run_current_stage`, expostos via `harness role` e `harness agent-run` — Fases 5 e 6 do `ROADMAP.md`, ✅ completas). Este documento descreve o comportamento já implementado — só o loop autônomo entre estágios (Fase 8) ainda falta.

## Contrato fundamental entre agentes e o Harness

Todo papel se comunica com o Harness através do **Agent Result Protocol** (✅ implementado, `harness/models.py` + `harness/controller.py::process_result_file`, comando `harness result PATH`):

```json
{
  "agent": "tester",
  "stage": "TESTING",
  "outcome": "FAIL",
  "summary": "2 tests failed",
  "artifacts": [".harness/tests/TEST_RESULTS.json"],
  "metadata": { "failed_tests": 2 }
}
```

Campos obrigatórios: `agent`, `stage`, `outcome`, `summary` (strings não vazias). Opcionais: `artifacts` (lista), `metadata` (objeto).

**Regra inegociável:** um agente relata o outcome (`SUCCESS`/`FAIL`/`PASS`); ele **nunca** escolhe o próximo estágio. O Harness aplica a tabela de transições de `harness/transitions.py`. Nenhum papel — incluindo o Maestro — pode contornar isso.

**Desde a Fase 3 (✅ completa), o Harness também pode sobrescrever o resultado da transição** — mesmo quando o agente reporta um outcome que normalmente continuaria o workflow — se `state.iteration.max` (10) for excedido ao entrar em `DIAGNOSIS`, ou se a mesma causa raiz se repetir 3+ vezes em diagnósticos consecutivos. Nos dois casos o Harness força `ESCALATED` em vez do próximo estágio esperado. Isso nunca aparece como erro pro agente que chamou `harness result` — o comando continua retornando normalmente, só que com `status: "ESCALATED"`.

## Papéis definidos (design; templates em `roles/*.md`)

### MAESTRO
Orquestração de alto nível: entender a tarefa, coordenar os demais papéis, fornecer contexto, monitorar progresso, recomendar ações. **Não decide transições** — apenas identifica qual papel deve agir a seguir e com qual artefato. Template: `roles/maestro.md` (já escrito, detalha responsabilidades, restrições, regras de escalonamento e formato de saída esperado).

### SPEC_ENGINEER
Converte o pedido do usuário em especificação precisa: objetivo, requisitos funcionais e não-funcionais, critérios de aceitação, restrições, dependências, riscos, suposições, itens fora de escopo. Artefato planejado: `.harness/spec/SPEC.md`. Template: `roles/spec-engineer.md`.

### PLANNER
Produz o plano de implementação: decisões de arquitetura, arquivos a modificar/criar, passos de implementação, dependências, estratégia de testes, riscos, considerações de rollback. Artefato planejado: `.harness/plan/PLAN.md`. Template: `roles/planner.md`.

### EXECUTOR
Responsável pela implementação: modificar código-fonte, criar arquivos, instalar dependências quando autorizado, seguir a especificação e o plano. **Não pode alegar sucesso sem produzir um resultado estruturado** (Agent Result Protocol). Template: `roles/executor.md`.

### TESTER
Valida a implementação: rodar testes, build, lint, testes de aceitação; coletar falhas; produzir resultados estruturados. Outcome sempre um de `PASS`, `FAIL`, `BLOCKED`. Artefatos planejados: `.harness/tests/`. Template: `roles/tester.md`.

### DEBUGGER
Diagnostica falhas: ler falhas de teste, inspecionar logs, identificar causa raiz, propor ou implementar correções, documentar o diagnóstico. Deve buscar a causa raiz em vez de aplicar correções aleatórias repetidamente. Artefato planejado: `.harness/diagnosis/DIAGNOSIS.md`. Template: `roles/debugger.md`.

**Contrato ativo com a Fase 3 (detecção de loop, ✅ completa):** ao reportar um resultado de `DIAGNOSIS` com outcome `SUCCESS` via `harness result`, inclua `metadata.root_cause` com um identificador curto e estável da causa raiz (o mesmo texto usado na seção "Root Cause" de `DIAGNOSIS.md` funciona bem). O Harness usa esse texto (hash normalizado por case/espaço) para detectar quando a mesma causa se repete — sem esse campo, ele cai no fallback do `summary`, que é menos preciso porque não foi desenhado pra ser um identificador estável. A seção "LOOP ANALYSIS" do template (`roles/debugger.md`) já pede pra comparar com iterações anteriores; `metadata.root_cause` é como essa observação chega até o Harness.

### REVIEWER
Revisa a implementação após os testes passarem: qualidade de código, consistência arquitetural, aderência à especificação, segurança, manutenibilidade, potenciais regressões. Outcomes: `PASS`/`FAIL`. Artefato planejado: `.harness/review/REVIEW.md`. Template: `roles/reviewer.md`.

### DOCUMENTER
Documentação final: atualizar README, documentar arquitetura, mudanças de API, configuração, decisões importantes; gerar o relatório final. Artefatos planejados: `.harness/documentation/`, `.harness/reports/FINAL_REPORT.md`. Template: `roles/documenter.md`.

## Mapeamento estágio → papel responsável

| Estágio do workflow | Papel responsável |
|---|---|
| TASK | MAESTRO |
| SPECIFICATION | SPEC_ENGINEER |
| PLANNING | PLANNER |
| EXECUTION | EXECUTOR |
| TESTING | TESTER |
| DIAGNOSIS | DEBUGGER |
| FIXING | EXECUTOR |
| REVIEW | REVIEWER |
| DOCUMENTATION | DOCUMENTER |

Esse mapeamento já está codificado em `harness/roles.py` (`STAGE_ROLE_MAP`) e é consultável via `harness role`. A Fase 6 (Claude Code Runner) já usa esse mapeamento pra invocar automaticamente um agente de IA de verdade via `harness agent-run`.

## Implementação atual dos papéis

Hoje, `harness/roles.py` já faz a diferenciação de papel em código: mapeia estágio → papel (`STAGE_ROLE_MAP`), resolve o caminho do template (`get_role_template_path`, relativo ao pacote — funciona de qualquer diretório) e carrega o conteúdo de `roles/*.md` programaticamente (`load_role_prompt`), montando o contexto do agente (`build_agent_context`: papel, artefato esperado, task id/title, resumo do último resultado, iteração atual). O comando `harness role` expõe esse mapeamento via CLI — mostra o estágio atual, o papel responsável, o caminho do template e o artefato esperado, útil pra um operador humano saber qual papel/prompt está em jogo em cada `harness agent-run`.

A execução automática já existe: `harness agent-run` invoca o Claude Code de verdade com esse contexto (`harness/agents/claude_code.py::ClaudeCodeRunner`). Um humano ou script externo ainda pode operar manualmente também, produzindo o JSON de resultado e rodando `harness result PATH` — os dois caminhos convergem no mesmo Agent Result Protocol. Não existe loop automático entre estágios ainda (Fase 8).

Depois do fato, `harness history` (Fase 9, parcial) mostra a timeline de quais papéis agiram, em qual ordem, com qual resultado e resumo — útil pra auditar uma sessão de trabalho manual guiada pelos papéis.
