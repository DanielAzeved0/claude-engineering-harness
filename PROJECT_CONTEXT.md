# PROJECT_CONTEXT.md

> Contexto permanente do projeto. Leia este documento (junto com `ARCHITECTURE.md`, `ROADMAP.md` e `AGENTS.md`) antes de implementar qualquer nova tarefa neste repositório. Ele não é uma descrição de tarefa pontual — é a definição do que esta aplicação pretende se tornar.

## Nome do projeto

**Claude Engineering Harness** (nome de produto possível no futuro: *Engineering Harness*). O nome pode mudar; a arquitetura e o propósito devem permanecer independentes da marca.

## Ideia central

O Claude Engineering Harness é um **controlador de workflow de engenharia autônomo**, projetado para orquestrar agentes de IA de codificação. O objetivo não é simplesmente pedir a uma IA que escreva código — é criar um **loop de engenharia controlado e repetível**:

```text
PROMPT → SPECIFICATION → PLANNING → EXECUTION → TESTING → PASS?
                                                              ├── YES → REVIEW → DOCUMENTATION → COMPLETE
                                                              └── NO  → DIAGNOSIS → FIXING → EXECUTION → TESTING → ↺
```

O loop deve continuar até: `SUCCESS`, `MAXIMUM ITERATIONS REACHED`, ou `THE TASK REQUIRES HUMAN INTERVENTION`.

Este é um **sistema de orquestração e controle de engenharia**, não um chatbot genérico.

## Objetivo primário (visão de produto)

O sistema deve eventualmente permitir que um usuário forneça um pedido de alto nível (ex.: "Crie um sistema de autenticação com JWT, login, registro, hashing de senha, rotas protegidas, testes e documentação") e o Harness coordene todo o processo de engenharia — do `TASK` ao `COMPLETE` — delegando cada etapa a um papel de agente especializado, mas mantendo o **controlador determinístico** como autoridade sobre as transições de estado.

**Status atual:** essa orquestração de ponta a ponta ainda **não existe**. Hoje o sistema requer que um humano (ou um script externo) rode `harness start` e produza os arquivos de resultado de agente; não há invocação automática de um agente de codificação. Veja `ROADMAP.md`.

## Agente de codificação principal

O agente de codificação primário deste projeto é o **Claude Code**, tratado como o agente de execução principal. Agentes futuros possíveis: Codex, Cursor, Aider, outros agentes OpenAI, agentes locais customizados.

O controlador deve, no entanto, ser **independente de agente** — a arquitetura separa `HARNESS CONTROLLER` de `AGENT RUNNER` para permitir trocar a implementação do agente no futuro. O `AGENT RUNNER` já está implementado (`harness/agents/`, comando `harness agent-run`) com uma interface abstrata (`AgentRunner`) e uma primeira implementação concreta (`ClaudeCodeRunner`); veja `ARCHITECTURE.md`.

## Princípio de design fundamental

> **A IA decide *como* executar o trabalho de engenharia. O Harness decide *o que pode acontecer em seguida.***

Exemplo: o Tester pode decidir que "os testes falharam porque o middleware de autenticação está incorreto" — mas o Tester **não decide** que o próximo estado é `FIXING`. O Harness aplica a tabela de transições: `TESTING + FAIL` sempre se torna `DIAGNOSIS`, de forma determinística. Esta separação é fundamental e não deve ser violada por nenhuma implementação futura (incluindo o papel MAESTRO — veja `AGENTS.md`).

## Princípios de engenharia (obrigatórios para mudanças futuras)

1. **Controle determinístico** — transições de workflow são sempre determinísticas, nunca decididas por inferência de um agente.
2. **Independência de agente** — o núcleo do Harness não deve depender exclusivamente do Claude Code.
3. **Artefatos em vez de memória** — informação importante do workflow deve ser persistida em disco (`.harness/`), não depender de contexto de conversação do agente.
4. **Validar antes de transicionar** — nunca transicionar com base em uma resposta de agente não validada.
5. **Sem loops infinitos** — todo mecanismo de retry deve eventualmente terminar ou escalar.
6. **Falhar com segurança** — resultados de agente malformados nunca devem corromper o estado.
7. **Fonte única de verdade** — as regras de transição permanecem centralizadas em `harness/transitions.py`; lógica de workflow não deve ser duplicada.
8. **Desenvolvimento incremental** — não implementar o roadmap inteiro de uma vez; cada fase deve ser implementada, compilada, testada, corrigida, validada e documentada antes da próxima.
9. **Testar o próprio Harness** — como o Harness controla outros processos de engenharia, sua própria corretude importa; toda funcionalidade importante do controlador deve ter testes automatizados.

## Não-objetivos (Non-Goals)

O projeto **não** pretende ser: um chatbot genérico; um substituto do Git; um substituto de CI/CD; um substituto do Claude Code; um simples wrapper de prompt; um sistema que tenta novamente indefinidamente sem limite.

## Integração futura com Maestri

O projeto pode futuramente integrar com [Maestri](https://www.themaestri.app/) como camada de visualização/orquestração de UI. O núcleo do Harness **não deve depender** do Maestri — o projeto deve permanecer funcional sem ele. Essa integração é posterior ao funcionamento do loop autônomo (Fase 6+) e **não existe nenhum código relacionado a ela hoje**.

## Como este documento deve ser usado

Para qualquer tarefa futura neste repositório:

1. Inspecionar o repositório existente.
2. Ler `PROJECT_CONTEXT.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `AGENTS.md`.
3. Entender a fase atual do desenvolvimento (`ROADMAP.md`).
4. Determinar se a funcionalidade pedida se encaixa na arquitetura.
5. Implementar sem reescrever código funcional desnecessariamente.
6. Adicionar/atualizar testes automatizados.
7. Rodar `python -m compileall harness` e a suíte de testes.
8. Corrigir falhas.
9. Atualizar esta documentação quando a arquitetura ou o comportamento mudar.
10. Reportar o que mudou, distinguindo sempre **implementação atual factual** de **arquitetura futura planejada**.

Nunca afirme que uma funcionalidade existe se ela não foi implementada e testada.
