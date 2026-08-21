# Competitive engine evidence

## Candidate and protocol

The submission candidate is `competitive`, a deterministic crop-first policy.
It buys four-carrot seed batches, selected from a same-seed local sweep of
4/8/12/16 units (seed 1: $4803/$4723/$4643/$4563), plants and waters on the planting day,
waits for the official two-day maturity threshold, harvests, routes carried
output to the shed, and sells only official market products. It retains animal
care actions for observed animals, but does not make animal expansion part of
the proven opening.

The harness stores normalized before/after snapshots on every JSONL turn event:
cash, position, hands, tile counts, shed, seeds, actions, fallback reason, and
latency. Run evidence with Python 3.11 and the optional competition group.

## Local official results

All results below use 720-turn local episodes, default official configuration,
the installed `kaggle-environments` Kaggriculture implementation, and zero
errors/fallbacks in every listed episode.

| Split | Opponent | Result | Average candidate money |
| --- | --- | --- | ---: |
| Development seeds 1–20 | PASS | 20 / 20 wins | 4829.75 |
| Development seeds 1–20 | official `random_agent` | 20 / 20 wins | 5317.25 |
| Development seeds 1–20 | `heuristic-v1` | 20 / 20 wins | 5219.35 |
| Confirmation seeds 21–40 | PASS | 20 / 20 wins | 5780.10 |
| Confirmation seeds 21–40 | official `random_agent` | 20 / 20 wins | 5400.65 |
| Confirmation seeds 21–40 | `heuristic-v1` | 20 / 20 wins | 4952.90 |
| Development seeds 1–20 | `competitive` self-play | 19 ties, 1 loss | 4064.25 |

The one self-play loss (seed 13, 5634 vs 5684) is a 50-money market-ordering
asymmetry. It produced no invalid action or fallback; self-play is retained as
a stability check, not a win-rate promotion gate.

## Reproduction

```bash
uv run --python 3.11 --group competition python -m agent.harness benchmark \
  --scenario competitive-pass-development
uv run --python 3.11 --group competition python -m agent.harness benchmark \
  --scenario competitive-random-development
uv run --python 3.11 --group competition python -m agent.harness benchmark \
  --scenario competitive-v1-development
uv run --python 3.11 --group competition python -m agent.harness benchmark \
  --scenario competitive-pass-confirmation
uv run --python 3.11 --group competition python -m agent.harness benchmark \
  --scenario competitive-random-confirmation
uv run --python 3.11 --group competition python -m agent.harness benchmark \
  --scenario competitive-v1-confirmation
```

The result files are generated evidence and remain outside the submission
archive. Re-run the matrix after any strategy or environment change.
