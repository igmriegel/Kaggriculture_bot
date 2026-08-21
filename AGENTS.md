# AGENTS.md

## Project mission

Build a robust, reproducible, and extensible Kaggriculture submission. The
project should first deliver a reliable local harness and a documented minimal
heuristic, then make it easy to add new rules, data-driven intelligence, and
reinforcement-learning models.

The minimum successful milestone is evidence of one successful submission and
an architecture that can be extended without rewriting the harness or the
submission boundary.

## Source of truth

- Treat the official Kaggriculture documentation and the installed
  `kaggle-environments` implementation as authoritative for observations,
  actions, game rules, limits, and submission format.
- Treat files under `docs/` as project design documents. When they conflict
  with official rules, update the docs and record the decision.
- Do not invent unknown fields or mechanics. Use nullable fields, adapters, or
  explicit TODOs until the source of truth is verified.

## Delivery priorities

1. Harness: adapter, typed contracts, action validation, fallback, runner,
   metrics, logs, smoke tests, and reproducible seeds.
2. Minimal heuristic: conservative, deterministic, well documented, and
   demonstrated with diagrams and benchmark evidence.
3. Submission packaging and end-to-end validation.
4. Extensions: richer rules, data-driven policies, RL, and hybrid engines.

The harness must remain strategy-agnostic. Strategy logic belongs in engines,
not in environment adapters or runners.

## Technical standards

- Python 3.11 or newer, managed with `uv`. The submission runtime is Python 3.11.
- Use Pydantic for externally-facing and normalized contracts where practical.
- Use Ruff for formatting and linting.
- Use Astral's `ty` for type checking.
- Use pytest for unit, integration, regression, and selected end-to-end tests.
- Use pre-commit to run all required quality gates.
- Prefer small typed modules, explicit interfaces, dependency injection, and
  deterministic behavior from explicit seeds.
- Project code and documentation are written in English.
- Use stable, current libraries for AI/modeling work, but keep the initial
  submission lightweight and free of unnecessary runtime model dependencies.

## Required validation

Before a change is considered complete, run the applicable pre-commit hooks,
Ruff, `ty`, pytest, and smoke tests. Submission-related changes must also run
the end-to-end package-generation and local Kaggriculture execution checks.

Tests should include:

- unit tests for state normalization, features, validation, and heuristic rules;
- integration tests against `kaggle_environments` when available;
- regression tests protecting previously fixed behavior;
- end-to-end tests proving that the generated package has `main.py` at its
  root and can complete a local episode.

## Uncertainty and technical debt

Do not block implementation for a decision that can be isolated safely. Create
an adapter or provisional interface, add a clearly scoped TODO or ADR, write a
test for the current behavior, and add the item to the project backlog. TODOs
must have an ownerable next action and should be removed as part of a continuous
technical-debt reduction flow.

Stop and ask for direction when an assumption could invalidate the submission,
change the competition contract, or materially expand scope.

## Documentation and diagrams

Every meaningful architectural decision must be reflected in the relevant
document. The minimal heuristic must describe its decision policy, safety
fallbacks, assumptions, and benchmark protocol. Use Mermaid or similarly
versionable diagrams to show the decision and execution flow.

When `graphify-out/graph.json` exists, use Graphify first for codebase
architecture, symbol-relationship, and data-flow questions. Its generated
artifacts are local development evidence, are ignored by Git, and must not be
included in a submission package. See `docs/operations/GRAPHIFY.md`.

## Git and collaboration

- Keep commits atomic: one coherent change per commit.
- Use semantic commit messages, e.g. `feat(harness): add action validator`.
- Do not mix refactors, generated artifacts, and unrelated fixes in one commit.
- Never commit credentials, local paths, notebooks, large reports, or generated
  submission artifacts unless explicitly required.
- Preserve existing user changes and inspect the worktree before editing.

## Definition of Done

A task is done only when its behavior is implemented, covered by appropriate
tests, validated by the required quality gates, documented, and its remaining
dependencies or TODOs are explicit. For an engine promotion, reproducible
benchmark evidence is required; a single favorable seed is insufficient.

## Working commands

The canonical commands are defined in `pyproject.toml`, `.pre-commit-config.yaml`,
and the project README as they are introduced. Prefer `uv run ...` so local and
CI execution use the same environment.
