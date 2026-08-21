# Proposed architecture

Read this document for system boundaries. For the current implementation map,
see [`HARNESS_IMPLEMENTATION.md`](HARNESS_IMPLEMENTATION.md).

## Princípios

- Separar decisão estratégica de execução turno a turno.
- Fazer toda ação passar por validação e fallback.
- Manter o schema do jogo isolado no adaptador de estado.
- Tornar decisões e métricas reproduzíveis por semente.
- Permitir trocar a engine sem trocar o executor.

## Componentes

| Componente | Responsabilidade |
|---|---|
| `main.py` | ponto de entrada da submissão |
| `agent/core` | protocol models and safety validation |
| `agent/harness` | adapters, runner, records, and reports |
| `engines` | heuristics, RL, and hybrid engines under one interface |
| `state` | normalization, temporal memory, and features |
| `planning` | tarefas, rotas, prioridades e execução segura |
| `market` | preços, demanda, lotes, reservas e vendas |
| `evaluation` | episódios, cenários, métricas e relatórios |
| `models` | artefatos aprovados, sem treinamento em runtime |

## Fluxo de decisão

```text
observação oficial
  -> adaptador/normalizador
  -> tracker e features
  -> engine estratégica
  -> planner de tarefas
  -> executor/validador
  -> ação ou PASS
  -> métricas e atualização do estado
```

## Contratos a confirmar

- formato exato da ação;
- ciclo de vida da observação;
- semântica de `PASS`;
- como o resultado final é informado;
- limites de tempo e memória;
- possibilidade de carregar arquivos do pacote.
