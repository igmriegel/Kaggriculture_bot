# Harness catalog

This is the canonical catalog of public harness structures. Update it in the
same commit as any public API change.

| Symbol | Public import | Owner | Purpose | Extend safely | Tests |
|---|---|---|---|---|---|
| `Action` | `agent.harness.Action` | core | validated game action | add optional protocol support in `core` | validation tests |
| `Observation` | `agent.harness.Observation` | core | permissive observation boundary | type verified nested fields only | contract tests |
| `RunConfig` | `agent.harness.RunConfig` | harness | seed, limits, logs, output | add optional defaulted fields | model tests |
| `TurnRecord` | `agent.harness.TurnRecord` | harness | one decision event | bump artifact version for breaking schema | reporting tests |
| `EpisodeRecord` | `agent.harness.EpisodeRecord` | harness | terminal episode evidence | preserve raw and normalized result | runner tests |
| `BenchmarkReport` | `agent.harness.BenchmarkReport` | harness | aggregate scenario evidence | require matching scenario fingerprint | benchmark tests |
| `EnvironmentAdapter` | `agent.harness.EnvironmentAdapter` | harness | official/fake environment lifecycle | implement and register an adapter | adapter contract tests |
| `Agent` | `agent.harness.Agent` | harness | raw action producer | implement and register a named agent | runner tests |
| `Reporter` | `agent.harness.Reporter` | harness | receives turn/episode events | implement and register a reporter | reporting tests |
| `Scenario` | `agent.harness.Scenario` | harness | immutable run matrix entry | add serializable config only | scenario tests |
| `EpisodeRunner` | `agent.harness.EpisodeRunner` | harness | one episode orchestration | extend via config/reporters, not strategy | runner tests |
| `register_adapter` / `get_adapter` | `agent.harness.register_adapter` / `agent.harness.get_adapter` | harness | adapter discovery | use unique stable names | registry tests |
| `register_agent` / `get_agent` | `agent.harness.register_agent` / `agent.harness.get_agent` | harness | agent discovery | use unique stable names | registry tests |
| `register_reporter` / `get_reporter` | `agent.harness.register_reporter` / `agent.harness.get_reporter` | harness | reporter discovery | use unique stable names | registry tests |
| `register_scenario` / `get_scenario` | `agent.harness.register_scenario` / `agent.harness.get_scenario` | harness | scenario discovery | use unique stable names | registry tests |

## Catalog invariants

- All facade exports appear in this table.
- Every row identifies an import path, owner, safe extension rule, and tests.
- Built-in registry names appear in `EXTENDING.md`.
- Documentation validation fails when catalog coverage or local links are stale.
