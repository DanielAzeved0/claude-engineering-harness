# AGENTS.md

> Descreve os papéis de agente (lógicos) do Claude Engineering Harness: suas responsabilidades, artefatos e limites. **Status atual: o mapeamento estágio → papel e o carregamento de templates já são código de produção** (`harness/roles.py`, exposto via `harness role`) — ver "Implementação atual dos papéis" abaixo. O que ainda não existe é a invocação automática de um agente de IA de verdade usando esse contexto; isso é trabalho da Fase 5 (`ROADMAP.md`), o Claude Code Runner. Este documento descreve tanto o comportamento já implementado quanto o *design pretendido* das fases seguintes.

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
Diagnostica falhas: ler falhas de teste, inspecionar logs, identificar causa raiz, propor ou implementar correções, documentar o diagnóstico. Deve buscar a causa raiz em vez de aplicar correções aleatórias repetidamente — este papel é o principal consumidor futuro da Fase 3 (Iteration Engine / detecção de loop). Artefato planejado: `.harness/diagnosis/DIAGNOSIS.md`. Template: `roles/debugger.md`.

### REVIEWER
Revisa a implementação após os testes passarem: qualidade de código, consistência arquitetural, aderência à especificação, segurança, manutenibilidade, potenciais regressões. Outcomes: `PASS`/`FAIL`. Artefato planejado: `.harness/review/REVIEW.md`. Template: `roles/reviewer.md`.

### DOCUMENTER
Documentação final: atualizar README, documentar arquitetura, mudanças de API, configuração, decisões importantes; gerar o relatório final. Artefatos planejados: `.harness/documentation/`, `.harness/reports/FINAL_REPORT.md`. Template: `roles/documenter.md`.

## Mapeamento estágio → papel responsável (planejado)

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

Esse mapeamento já está codificado em `harness/roles.py` (`STAGE_ROLE_MAP`) e é consultável via `harness role`. O que falta é a Fase 5 (Claude Code Runner) invocar automaticamente um agente de IA de verdade usando esse contexto.

## Implementação atual dos papéis

Hoje, `harness/roles.py` já faz a diferenciação de papel em código: mapeia estágio → papel (`STAGE_ROLE_MAP`), resolve o caminho do template (`get_role_template_path`) e carrega o conteúdo de `roles/*.md` programaticamente (`load_role_prompt`), montando o contexto do agente (`build_agent_context`). O comando `harness role` expõe esse mapeamento via CLI. O que ainda não existe é a execução automática: nenhum agente de IA de verdade é invocado com esse contexto — os papéis continuam sendo executados manualmente, por um humano ou por um script/agente externo ao Harness que produz o JSON de resultado e roda `harness result PATH`. Isso é trabalho da Fase 5 (Claude Code Runner).
