# Extending the harness

## Adapter

Implement `EnvironmentAdapter`, keep official-library details inside
`agent/harness/adapters/`, add deterministic fake-adapter tests, register a
unique name, and document the name below.

## Agent

Implement `Agent.act(observation) -> raw action`. Never validate or send the
action directly; the runner owns fallback and evidence. Register the agent by a
stable name.

## Reporter

Implement `Reporter.on_turn` and `Reporter.on_episode`. Reporters must not
alter runner control flow. JSON and JSONL reporters are built-ins.

## Scenario

Create a serializable `Scenario` using registered adapter, agent, and opponent
names plus configuration and explicit seeds. Its fingerprint identifies a
comparable benchmark matrix.

## Required checklist

1. Add or update the public catalog row.
2. Register the component and test discovery/duplicate-name failure.
3. Add unit and contract tests using deterministic fixtures.
4. Update artifact/version compatibility when record output changes.
5. Run all quality gates and commit atomically.

## Built-in names

| Registry | Name | Purpose |
|---|---|---|
| adapter | `kaggriculture` | official advanced environment |
| reporter | `json` | episode and benchmark summaries |
| reporter | `jsonl` | per-turn event stream |
