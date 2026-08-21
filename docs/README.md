# Kaggriculture documentation

This is the documentation entry point. Read [`../AGENTS.md`](../AGENTS.md)
once per work session, then use the task router below.

## Task router

| Task | Read first | Then inspect |
|---|---|---|
| Change harness runtime | [`harness/README.md`](harness/README.md) | `agent/harness/` |
| Add adapter, reporter, or scenario | [`harness/EXTENDING.md`](harness/EXTENDING.md) | [`harness/CATALOG.md`](harness/CATALOG.md) |
| Diagnose an episode | [`harness/OPERATIONS.md`](harness/OPERATIONS.md) | JSON/JSONL artifacts |
| Change game contracts | [`architecture/ARCHITECTURE.md`](architecture/ARCHITECTURE.md) | `agent/core/` |
| Change an engine | [`engines/HEURISTIC_MVP.md`](engines/HEURISTIC_MVP.md) | `agent/engines/` |
| Benchmark or submit | [`operations/BENCHMARKS.md`](operations/BENCHMARKS.md) | [`operations/SUBMISSION.md`](operations/SUBMISSION.md) |
| Query code relationships | [`operations/GRAPHIFY.md`](operations/GRAPHIFY.md) | `graphify-out/graph.json` |
| Choose or review a design | [`architecture/DECISIONS.md`](architecture/DECISIONS.md) | [`operations/BACKLOG.md`](operations/BACKLOG.md) |

## Documentation ownership

- `harness/`: public harness contract, catalog, extension workflow, and operations.
- `architecture/`: boundaries and accepted technical decisions.
- `engines/`: engine-specific behavior and safety rules.
- `operations/`: backlog, benchmarks, roadmap, and submission process.
- `agents/`: agent operating workflow and handoff format.

Every public `agent.harness` symbol must be listed in
[`harness/CATALOG.md`](harness/CATALOG.md). Every new document must be linked
from this index or its domain index.
