# Harness implementation map

This is the short operational companion to [`HARNESS.md`](HARNESS.md). Read
this file when implementing or reviewing harness code; read `HARNESS.md` when
changing the protocol or acceptance criteria.

## Current map

| Contract | Implementation | Tests | Status |
|---|---|---|---|
| Action model | `agent/core/contracts.py` | `tests/test_validation.py` | implemented |
| Observation boundary | `agent/core/contracts.py` | pending richer fixtures | provisional |
| Action validation/fallback | `agent/core/validation.py` | `tests/test_validation.py` | implemented |
| Environment adapter protocol | `agent/harness/protocols.py` | `tests/test_runner.py` fake adapter | provisional |
| Episode and turn records | `agent/harness/models.py` | `tests/test_runner.py` | implemented |
| Single episode runner | `agent/harness/runner.py` | `tests/test_runner.py` | implemented |
| Official Kaggle adapter | not created | pending | next P0 |
| Batch benchmark runner | not created | pending | next P1 |
| JSON/JSONL report writer | not created | pending | next P1 |
| Submission package validator | not created | pending | next P0 |

## Boundary rules

- `agent/core/` owns protocol models and safety validation.
- `agent/harness/` owns execution, records, adapters, and reporting.
- `agent/engines/` returns candidate actions; it does not validate the
  environment contract.
- `main.py` is the only submission entry point and must remain importable from
  the package root.
- Fallbacks must be observable in episode records and never silently hide an
  agent failure.

## Next implementation slice

1. Add an adapter around `kaggle_environments.make("kaggriculture")`.
2. Preserve raw observations and results while normalizing verified fields.
3. Add a short-episode smoke test against `random` and self-play.
4. Add JSONL turn logs and JSON episode reports.
5. Add package generation and external-directory execution tests.

The optional `competition` dependency group exists because the environment can
require native SDL/Freetype support through `pygame`; local unit gates must not
depend on those native libraries.
