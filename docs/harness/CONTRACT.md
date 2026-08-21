# Harness contract

## Responsibilities

- Create and run deterministic episodes through an `EnvironmentAdapter`.
- Validate candidate actions and substitute `PASS` while recording the reason.
- Classify normal completion, agent errors, environment errors, timeouts, and
  safety-limit termination.
- Emit versioned JSON episode/benchmark summaries and optional JSONL turn events.
- Resolve adapters, agents, reporters, and scenarios through explicit registries.

## Boundaries

- `agent.core` owns game protocol models and validation.
- `agent.harness` owns execution and evidence.
- `agent.engines` returns candidate actions only.
- `main.py` remains the competition entry point; it does not own harness logic.

## Compatibility

The public facade is the compatibility boundary. New model fields are optional
and defaulted; artifact schema changes require a schema-version increment.
Internal module rearrangement is allowed if facade imports, registry names, and
artifact versions remain compatible.
