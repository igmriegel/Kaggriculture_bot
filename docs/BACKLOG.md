# Backlog

Use this as the ordered work queue. Each item needs implementation, evidence,
documentation, and explicit dependencies before it is complete.

Prioridade: **P0** bloqueia uma submissão mínima; **P1** melhora robustez;
**P2** é experimento ou otimização.

## Current focus: harness

The provisional contracts, validation, fake-adapter runner, and minimal
heuristic are implemented. The next slice is the official environment adapter
and a real local episode. See [`HARNESS_IMPLEMENTATION.md`](HARNESS_IMPLEMENTATION.md)
for the code-to-contract map.

Antes de implementar o agente, concluir e revisar o contrato descrito em
[`HARNESS.md`](HARNESS.md). As tarefas H0.x abaixo são a primeira fila de trabalho.

| ID | Prioridade | Tarefa | Dependência | Saída esperada |
|---|---|---|---|---|
| H0.1 | P0 | confirmar schema do ambiente | regras oficiais | contrato de observação/ação |
| H0.2 | P0 | definir `EpisodeRecord` e erros | H0.1 | modelo de evidência |
| H0.3 | P0 | definir adaptador do ambiente | H0.1 | interface de execução |
| H0.4 | P0 | definir validação e fallback | H0.2 | contrato de segurança |
| H0.5 | P0 | definir smoke tests | H0.3, H0.4 | matriz de cenários |
| H0.6 | P1 | definir formato de logs | H0.2 | JSON/JSONL versionado |
| H0.7 | P1 | definir matriz de benchmark | H0.2 | protocolo comparável |
| H0.8 | P1 | definir validação do pacote | regras oficiais | checklist automatizável |

Depois de H0.1–H0.5 aprovadas, iniciar a implementação do harness; as tarefas
de engine permanecem bloqueadas até que o runner mínimo seja confiável.

Current status: H0.2, H0.3, and H0.4 have provisional code and unit tests;
H0.1, H0.5, H0.6, H0.7, and H0.8 remain open until the official adapter exists.

| ID | Prioridade | Tarefa | Dependência | Saída esperada |
|---|---|---|---|---|
| F0.1 | P0 | confirmar regras e schema | acesso à competição | contrato documentado |
| F0.2 | P0 | definir ambiente Python | F0.1 | instalação reproduzível |
| F0.3 | P0 | agente `PASS` | F0.1 | partida mínima |
| F0.4 | P0 | runner e métricas | F0.3 | relatório por semente |
| F1.1 | P0 | normalizar observação | F0.1 | estado tipado |
| F1.2 | P1 | tracker temporal | F1.1 | features de ciclo |
| F1.3 | P1 | modelo econômico | F1.1 | retorno estimado |
| F2.1 | P0 | mapa e rotas | F1.1 | alvos alcançáveis |
| F2.2 | P0 | tarefas e executor | F2.1 | ações validadas |
| F2.3 | P1 | matriz de falhas | F2.2 | cenários seguros |
| F3.1 | P0 | heurística conservadora | F2.2 | baseline |
| F3.2 | P1 | benchmark do baseline | F0.4, F3.1 | tabela comparável |
| F4.1 | P2 | dataset de episódios | F3.2 | dados versionados |
| F4.2 | P2 | ambiente RL alto nível | F4.1 | API de treino |
| F5.1 | P2 | treinamento progressivo | F4.2 | checkpoints |
| F6.1 | P2 | integração híbrida | F5.1 | candidata híbrida |
| F7.1 | P0 | pacote Kaggle | F3.1 | arquivo submetível |
| F7.2 | P0 | teste externo e limites | F7.1 | checklist aprovado |

## Definition of Done

Uma tarefa só sai de “a fazer” quando tem saída verificável, teste ou evidência
correspondente, documentação atualizada e dependências identificadas.
