# Harness implementation map

| Capability | Module | Status | Next growth step |
|---|---|---|---|
| Core contracts/state | `agent/core/` | partial | fixtures for nested official-state models |
| Public facade | `agent/harness/__init__.py` | implemented | export only catalogued symbols |
| Registries | `agent/harness/registry.py` | implemented | add explicit names and diagnostics |
| Episode execution | `agent/harness/execution.py` | implemented | enforce hard process timeouts if required |
| Official adapter | `agent/harness/adapters/kaggle.py` | partial | validate against optional native competition stack |
| Artifacts | `agent/harness/reporting.py` | implemented | add artifact migrations on schema change |
| Scenarios/benchmarks | `agent/harness/scenarios.py` | implemented | official-horizon evidence matrix |
| CLI | `agent/harness/cli.py` | implemented | smoke/run/benchmark/report/package validation |

The current Kaggle adapter accepts PASS, deterministic random, and registered
self-play opponents. Official smoke coverage remains pending an
environment-installed integration test.
