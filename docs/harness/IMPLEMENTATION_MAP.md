# Harness implementation map

| Capability | Module | Status | Next growth step |
|---|---|---|---|
| Core contracts | `agent/core/` | partial | nested official-state models |
| Public facade | `agent/harness/__init__.py` | planned | export only catalogued symbols |
| Registries | `agent/harness/registry.py` | planned | built-in names and diagnostics |
| Episode execution | `agent/harness/execution.py` | partial | timeout and terminal classifications |
| Official adapter | `agent/harness/adapters/kaggle.py` | planned | short smoke episode |
| Artifacts | `agent/harness/reporting.py` | planned | JSON/JSONL versioning |
| Scenarios/benchmarks | `agent/harness/scenarios.py` | planned | fixed seed matrices |
| CLI | `agent/harness/cli.py` | planned | smoke/run/benchmark/report/package validation |
