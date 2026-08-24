# Harness implementation map

| Capability | Module | Status | Next growth step |
|---|---|---|---|
| Core contracts/state | `agent/core/` | partial | immutable normalized public farms, private shed/seeds, and per-unit inventories; prevent engines reading raw observations |
| Public facade | `agent/harness/__init__.py` | implemented | export only catalogued symbols |
| Registries | `agent/harness/registry.py` | implemented | add explicit names and diagnostics |
| Episode execution | `agent/harness/execution.py` | implemented | enforce hard process timeouts if required |
| Official adapter | `agent/harness/adapters/kaggle.py` | partial | validate official farmer/hand/market wire actions and capture native fixtures |
| Artifacts | `agent/harness/reporting.py`, `agent/harness/html_reports.py` | implemented | add artifact migrations on schema change |
| Scenarios/benchmarks | `agent/harness/scenarios.py` | partial | fixed 720-turn PASS/random/self-play matrix and official fixture replay |
| CLI | `agent/harness/cli.py`, `scripts/update_submission_reports.py`, `Makefile` | implemented | smoke/run/benchmark/report/package validation and HTML submission refresh |

| Hands and action validation | `agent/core/`, `agent/harness/adapters/` | gap | ordered hand actions, legal action families, and safe no-op records |
| Inventory and shed logistics | future `agent/core/` models and engine services | gap | per-unit inventory, shed access tiles, capacity, and overflow accounting |
| Crops and weeds | future crop domain module | gap | plant lifecycle, same-day watering, harvesting, fertilizer, and weed clearing |
| Animal structures | future animal domain module | gap | coop/pasture, animal care/feed, products, and fertilizer collection |
| Land quadrants | future land domain module | gap | unlock sequence, locked tiles, and purchase safety |
| Town demand and market | future market domain module | gap | shop instances, town-center demand, prices, and order-limit valuation |
| Official fixtures | `tests/fixtures/` (planned) | gap | initial, lifecycle, invalid/no-op, market, land, and terminal-reward snapshots |

The current adapter accepts PASS, deterministic random, and registered
self-play opponents. Its advanced-game coverage is not evidence that the
unimplemented action families are valid until fixture and integration coverage
is added.
