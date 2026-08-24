# Benchmarks

Compare engines only under matching scenario fingerprints: same adapter,
opponents, configuration, horizon, and explicit seed set. Track win rate,
money, variance, errors, invalid fallbacks, latency, loss events, and overflow.

Promote an engine only with repeatable improvement over the current baseline.

For the hybrid portfolio comparison, run `leader-v2-*` and `leader-v3-*` with
the same PASS, random, and competitive opponents. Development uses seeds 1–20;
confirmation uses seeds 41–80. Promotion requires V3 to meet or exceed V2's
mean money in every matching scenario, improve the aggregate worst quartile,
and not reduce win rate. Reports must retain per-episode portfolio metrics:
animals, crops, sales value, feeding lost, escaped animals, pending
irrigation, stock wasted, and hand utilization.
