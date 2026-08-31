# AGENTS.md

> Descreve os papéis de agente (lógicos) do Claude Engineering Harness: suas responsabilidades, artefatos e limites. **Status atual: nenhum destes papéis é invocado automaticamente pelo código hoje.** Os templates de prompt já existem como arquivos estáticos em `roles/*.md`, mas nada em `harness/*.py` os carrega ou executa — isso é trabalho da Fase 4 (`ROADMAP.md`). Este documento descreve o *design pretendido*, não uma funcionalidade em produção.

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

Esse mapeamento ainda não está codificado em `harness/*.py` — é a base conceitual para a Fase 4.

## Implementação atual dos papéis

Hoje, **todos os papéis são executados manualmente** — por um humano ou por um script/agente externo ao Harness que produz o JSON de resultado e roda `harness result PATH`. Não há diferenciação de prompt, contexto ou modelo por papel dentro do código Python; isso é puramente convenção de uso até a Fase 4/5 serem implementadas. Os templates em `roles/*.md` podem ser usados manualmente (copiados para uma sessão de Claude Code, por exemplo) como guia de comportamento esperado para cada papel, mas não são carregados programaticamente.
