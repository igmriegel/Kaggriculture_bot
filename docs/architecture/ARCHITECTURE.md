# Architecture

```text
official observation
  -> agent.core contracts
  -> engine proposes raw action
  -> agent.harness validation and execution
  -> official environment
  -> records, reporters, and benchmark artifacts
```

`agent.core` is game-domain code. `agent.harness` is reusable execution
infrastructure. `agent.engines` contains strategy. New planning, market, or RL
modules must depend on the public harness facade rather than its internals.
