# Harness implementation map

| Capability | Module | Status | Next growth step |
|---|---|---|---|
| Core contracts | `agent/core/` | partial | nested official-state models |
| Public facade | `agent/harness/__init__.py` | implemented | export only catalogued symbols |
| Registries | `agent/harness/registry.py` | implemented | add explicit names and diagnostics |
| Episode execution | `agent/harness/execution.py` | implemented | enforce hard process timeouts if required |
| Official adapter | `agent/harness/adapters/kaggle.py` | partial | validate against optional native competition stack |
| Artifacts | `agent/harness/reporting.py` | implemented | add artifact migrations on schema change |
| Scenarios/benchmarks | `agent/harness/scenarios.py` | partial | fixed seed matrices and opponent support |
| CLI | `agent/harness/cli.py` | partial | smoke/run/benchmark/report/package validation |

The current Kaggle adapter defaults to a `PASS` opponent. Official `random` and
self-play smoke coverage are pending an environment-installed integration test.
