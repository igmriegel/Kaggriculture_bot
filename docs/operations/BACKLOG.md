# Backlog

## P0

1. Add immutable normalized contracts for every verified observation field and
   farmer/hand/market action family; prohibit strategy access to raw mappings.
2. Capture official fixtures for initial state, crop lifecycle, weeds, shed
   overflow, animal lifecycle, market orders, land purchase, town changes,
   invalid/no-op actions, and terminal rewards.
3. Replay every fixture as a contract test, asserting either valid output or a
   recorded safe fallback.
4. Complete the fixed full-720-turn PASS, random, and self-play matrix across
   multiple explicit seeds with zero unhandled errors and unsupported actions.

## P1

1. Implement V2 crop/shed catalog, obligation precedence, route selection,
   overflow avoidance, reserve-aware purchases, and final liquidation.
2. Add named scenarios, batch benchmarks, and reports for completion, reward,
   outcomes, errors, fallbacks, latency, loss, overflow, unsold inventory,
   action-family counts, and economics.
3. Implement V3 ordered hands, Fibonacci hiring analysis, and safe land
   purchase planning.
4. Run the leader-inspired engine through the official multi-seed matrix and
   promote it only if replay fidelity and safety evidence remain reproducible.
5. Spatial Movement Optimization & Concentric Zoning: concentric crop/animal placement
   relative to Shed (0,0), optimal worker-to-task assignment (bipartite matching),
   and contiguous route chaining to minimize walking turns.

## P2

1. Implement V4 animal lifecycle and dynamic town-market valuation.
2. Dataset collection, strategic RL, and hybrid policy evaluation.
