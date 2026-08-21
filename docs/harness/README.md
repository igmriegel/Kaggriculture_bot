# Harness start here

The harness is a strategy-agnostic execution library for Kaggriculture. It
owns environment lifecycle, action safety, records, artifacts, and benchmark
orchestration; engines only propose actions.

| Need | Read | Extend through |
|---|---|---|
| Change public behavior | [`CONTRACT.md`](CONTRACT.md) | `agent.harness` facade |
| Find a symbol | [`CATALOG.md`](CATALOG.md) | documented import path |
| Add a component | [`EXTENDING.md`](EXTENDING.md) | named registry |
| Run or diagnose | [`OPERATIONS.md`](OPERATIONS.md) | CLI and artifacts |
| Review current coverage | [`IMPLEMENTATION_MAP.md`](IMPLEMENTATION_MAP.md) | source and tests |

Do not import `agent.harness` internals from engines, CLIs, or external tools.
Use the facade or registered names.
