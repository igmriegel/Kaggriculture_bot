# Kaggriculture documentation

This directory is organized for selective reading. Start with the routing table
below, read the required documents for the task, and only then open optional
background material.

## Task routing

| Task | Required reading | Optional reading | Main code |
|---|---|---|---|
| Understand project rules | [`AGENTS.md`](../AGENTS.md) | [`DECISIONS.md`](DECISIONS.md) | — |
| Work on the harness | [`HARNESS.md`](HARNESS.md), [`HARNESS_IMPLEMENTATION.md`](HARNESS_IMPLEMENTATION.md) | [`ARQUITETURA_PROPOSTA.md`](ARQUITETURA_PROPOSTA.md) | `agent/harness/`, `agent/core/` |
| Work on state/features | [`ARQUITETURA_PROPOSTA.md`](ARQUITETURA_PROPOSTA.md), [`BACKLOG.md`](BACKLOG.md) | [`PLANO_COMPETICAO_KAGGRICULTURE.md`](PLANO_COMPETICAO_KAGGRICULTURE.md) | `agent/core/` |
| Work on heuristic engines | [`MVP_HEURISTIC.md`](MVP_HEURISTIC.md), [`ARQUITETURA_PROPOSTA.md`](ARQUITETURA_PROPOSTA.md) | [`EXPERIMENTOS_E_BENCHMARKS.md`](EXPERIMENTOS_E_BENCHMARKS.md) | `agent/engines/` |
| Work on benchmarks | [`EXPERIMENTOS_E_BENCHMARKS.md`](EXPERIMENTOS_E_BENCHMARKS.md), [`HARNESS.md`](HARNESS.md) | [`BACKLOG.md`](BACKLOG.md) | `agent/harness/` |
| Prepare a submission | [`CHECKLIST_SUBMISSAO.md`](CHECKLIST_SUBMISSAO.md), [`HARNESS_IMPLEMENTATION.md`](HARNESS_IMPLEMENTATION.md) | official competition docs | `main.py` |
| Plan a new phase | [`BACKLOG.md`](BACKLOG.md), [`PLANO_COMPETICAO_KAGGRICULTURE.md`](PLANO_COMPETICAO_KAGGRICULTURE.md) | [`DECISIONS.md`](DECISIONS.md) | — |

## Document map

- [`AGENT_GUIDE.md`](AGENT_GUIDE.md): short operating procedure for agents.
- [`HARNESS.md`](HARNESS.md): environment-agnostic harness contract and acceptance criteria.
- [`HARNESS_IMPLEMENTATION.md`](HARNESS_IMPLEMENTATION.md): current code mapping and next steps.
- [`ARQUITETURA_PROPOSTA.md`](ARQUITETURA_PROPOSTA.md): boundaries between state, engines, planning, and submission.
- [`MVP_HEURISTIC.md`](MVP_HEURISTIC.md): first policy and its safety priorities.
- [`EXPERIMENTOS_E_BENCHMARKS.md`](EXPERIMENTOS_E_BENCHMARKS.md): reproducible evaluation protocol.
- [`BACKLOG.md`](BACKLOG.md): ordered work queue with dependencies and evidence.
- [`CHECKLIST_SUBMISSAO.md`](CHECKLIST_SUBMISSAO.md): package and external-validation checklist.
- [`DECISIONS.md`](DECISIONS.md): decisions, assumptions, and technical debt.
- [`PLANO_COMPETICAO_KAGGRICULTURE.md`](PLANO_COMPETICAO_KAGGRICULTURE.md): product plan and phase gates.

## Reading rules

1. Read `AGENTS.md` once per work session.
2. Read only the task row's required documents before editing.
3. Read optional documents when a dependency or decision requires them.
4. Update the relevant contract and backlog item when behavior changes.
5. Link new documents from this index; an unindexed document is not part of the workflow.

## Source of truth

Official Kaggriculture rules and the installed `kaggle-environments` implementation
override planning assumptions. The current official entry point is a `main.py`
file exposing `agent`, with advanced observations containing public farm state,
market, town, and private inventory data. See the official
[`kaggriculture README`](https://github.com/Kaggle/kaggle-environments/blob/master/kaggle_environments/envs/kaggriculture/README.md)
before changing the adapter.
