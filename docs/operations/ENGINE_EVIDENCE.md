# Engine evidence

## Candidate and protocol

The submission candidate is `leader-v2`, a deterministic full-cycle planner
inspired by leader replay behavior. It sets daily budgets, gives production
goals deadlines, reserves every worker to one target, and only expands animals
when their structure, placement, feed, care, and output chain can operate.
It sells using projected prices and storage pressure rather than liquidating
every item immediately.

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

## Leader V2 promotion evidence

`leader-v2` completed its development and independent confirmation matrices
with zero errors and fallbacks. The confirmation threshold was at least 75%
wins against PASS and 50% against random and `competitive`.

| Split | Opponent | Result | Average candidate money |
| --- | --- | --- | ---: |
| Development seeds 1–20 | PASS | 20 / 20 wins | 14891.45 |
| Development seeds 1–20 | official `random_agent` | 20 / 20 wins | 15449.80 |
| Development seeds 1–20 | `competitive` | 20 / 20 wins | 13964.85 |
| Confirmation seeds 41–80 | PASS | 40 / 40 wins | 14746.25 |
| Confirmation seeds 41–80 | official `random_agent` | 40 / 40 wins | 15656.20 |
| Confirmation seeds 41–80 | `competitive` | 40 / 40 wins | 14776.02 |

The confirmation fingerprints are PASS `ad8ac6f0ea1f96fa`, random
`acb6b780eb24e591`, and `competitive` `1da3584718e6536f`.

## Reproduction

```bash
uv run --python 3.11 --group competition python -m agent.harness benchmark \
  --scenario leader-v2-pass-development
uv run --python 3.11 --group competition python -m agent.harness benchmark \
  --scenario leader-v2-random-development
uv run --python 3.11 --group competition python -m agent.harness benchmark \
  --scenario leader-v2-competitive-development
uv run --python 3.11 --group competition python -m agent.harness benchmark \
  --scenario leader-v2-pass-confirmation
uv run --python 3.11 --group competition python -m agent.harness benchmark \
  --scenario leader-v2-random-confirmation
uv run --python 3.11 --group competition python -m agent.harness benchmark \
  --scenario leader-v2-competitive-confirmation
```

The result files are generated evidence and remain outside the submission
archive. Re-run the matrix after any strategy or environment change.
