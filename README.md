# Kaggriculture Bot 🌾

> A safe, reproducible starting point for building a Kaggriculture agent —
> with a local harness, deterministic heuristics, evidence artifacts, and a
> submission package you can inspect before uploading.

This repository is designed for a simple goal: make experimentation with a
farm-playing agent feel calm and dependable. Strategy code stays separate from
the game adapter and runner, so you can improve the bot without rewriting the
submission boundary each time.

The current submission candidate is **`competitive`**. It plans actions for
the farmer and every active hand, prioritising yield, watering, feeding,
weeds, collection, shed capacity, and safe liquidation. When a command cannot
be established from the observation, the submission boundary falls back to
`PASS` rather than inventing a mechanic.

## What is included

- A typed action boundary with a final safety validator.
- A strategy-agnostic episode runner with deterministic seeds and time limits.
- JSON episode reports and optional JSONL decision traces.
- Built-in PASS, deterministic-random, and self-play scenarios.
- Three engines: a conservative baseline, `heuristic-v1`, and `competitive`.
- A submission packager that produces a tarball with `main.py` at its root.
- Unit tests and quality gates for the public harness and the V1 policy.

## Quick start

The project targets **Python 3.11+** and uses [uv](https://docs.astral.sh/uv/).

```bash
git clone <your-fork-url>
cd Kaggriculture_bot
uv sync
```

Run the local quality checks:

```bash
uv run ruff format --check agent tests
uv run ruff check agent tests
uv run ty check agent tests
uv run pytest
```

## Build a submission

Create a small, portable archive:

```bash
uv run python -m agent.harness package-submission \
  --output dist/kaggriculture-submission.tar.gz

uv run python -m agent.harness validate-submission \
  --path dist/kaggriculture-submission.tar.gz
```

The archive contains only `main.py` and runtime Python modules. It deliberately
excludes reports, tests, documentation, local paths, and Graphify artifacts.
Upload the resulting tarball manually through Kaggle once it has passed your
local evidence checks.

## Run scenarios and collect evidence

The optional competition dependency provides the official local environment:

```bash
uv sync --group competition

uv run --group competition python -m agent.harness benchmark --scenario v1-pass
uv run --group competition python -m agent.harness benchmark --scenario v1-random
uv run --group competition python -m agent.harness benchmark --scenario v1-self-play
```

Each scenario uses explicit seeds. Results are written as versioned JSON under
`reports/`; add `--log-turns` to a `run` or `smoke` command for a JSONL stream
of turn-level actions, fallbacks, exceptions, and latency.

> **Note:** the official environment is optional. If its native dependencies
> are unavailable on your machine, unit tests and package validation still run;
> complete the official smoke matrix on a compatible host before submitting.

## How the bot is structured

```mermaid
flowchart LR
    O[Official observation] --> C[agent.core]
    C --> E[agent.engines]
    E --> V[Action validation]
    V --> K[Kaggriculture environment]
    K --> H[agent.harness]
    H --> R[JSON / JSONL evidence]
```

| Area | Responsibility |
|---|---|
| `agent/core/` | Contracts, state normalization, and action validation. |
| `agent/engines/` | Decision policies such as `heuristic-v1`. |
| `agent/harness/` | Environment lifecycle, scenarios, reporting, and CLI workflows. |
| `main.py` | Kaggle submission entry point. |
| `tests/` | Regression coverage for policy, harness, artifacts, and packaging. |
| `docs/` | Architecture decisions, operational guides, and engine notes. |

## Competitive engine, in plain language

The competitive engine allocates one legal task per available unit:

1. Harvest held crop or animal output, then water and feed obligations.
2. Remove weeds, collect fertilizer, care for animals, and route inventories to the shed.
3. Divide remaining watering, harvesting, cleanup, and planting targets among hands.
4. Sell before shed overflow and liquidate known shed stock near the season close.
5. Buy a bounded number of economically ranked seeds while retaining cash reserve.

This is intentionally not an all-knowing economic model yet. Animal care,
workers, fertilizer, land purchases, and advanced market rules will be enabled
only after their official fields and preconditions are captured in fixtures.
That restraint is a feature: the submission boundary should never invent game
mechanics.

Read the [engine policy](docs/engines/HEURISTIC_V1.md) for verified protocol
constraints, safeguards, and promotion criteria.

## Development workflow

Before opening a pull request or building a candidate, run:

```bash
uv run pre-commit run --all-files
```

Useful references:

- [Architecture](docs/architecture/ARCHITECTURE.md)
- [Harness guide](docs/harness/README.md)
- [Benchmark protocol](docs/operations/BENCHMARKS.md)
- [Submission guide](docs/operations/SUBMISSION.md)
- [Backlog](docs/operations/BACKLOG.md)

## Status

The project has a validated local harness and an isolated, packageable V1
candidate. Official full-horizon benchmark evidence and richer farm mechanics
remain the next milestones. See the [backlog](docs/operations/BACKLOG.md) for
the exact follow-up work.

---

Built for reliable iteration first — then smarter farming. 🌱
