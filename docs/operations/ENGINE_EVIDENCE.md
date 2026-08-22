# Engine evidence

## Candidate and protocol

The submission candidate is `leader-v2`, a deterministic full-cycle planner
derived from leader replay phases. It reproduces the replay opening without
copying coordinates or seeds: wait one turn, build a pasture, hire five hands,
then buy four animals, melon/wheat seeds, and wheat feed. Its daily planner
reserves feed collection before animal work, then builds, places, plants, and
waters in opening order.

All results below use 720-turn local episodes, default official configuration,
the installed `kaggle-environments` Kaggriculture implementation, and seeds
1–20. Reports are generated evidence and remain outside the submission archive.

## Reproduced development results

| Split | Opponent | Result | Average candidate money |
| --- | --- | --- | ---: |
| Development seeds 1–20 | PASS | 20 / 20 wins | 29641.15 |
| Development seeds 1–20 | official `random_agent` | 20 / 20 wins | 20564.75 |

Both matrices completed with zero agent errors and zero validation fallbacks.
The PASS liquidity guard raised the lowest seed to $23574 (seed 4), including
seed 17 from $3274 to $29550. The public leader replays still set the higher
target: $82750–$163990.

## Remaining promotion gates

1. Run the matching development matrix against `competitive`.
2. Repeat PASS, random, and `competitive` on independent confirmation seeds.
3. Compare day 0/1/6/12/18/24 milestones against both leader replay audits;
   investigate any low-tail seed before submitting.

## Reproduction

```bash
uv run --python 3.11 --group competition python -m agent.harness benchmark \
  --scenario leader-v2-pass-development
uv run --python 3.11 --group competition python -m agent.harness benchmark \
  --scenario leader-v2-random-development
uv run --python 3.11 --group competition python -m agent.harness benchmark \
  --scenario leader-v2-competitive-development
```
