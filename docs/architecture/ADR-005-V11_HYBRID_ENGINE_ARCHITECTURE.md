# ADR-005: V11 Hybrid Engine Architecture

## Status

Accepted (Promoted to Primary Submission Candidate)

## Context

Previous engine iterations (V8, V9, V9.2) relied on static calendar day cutoffs, greedy single-turn spatial matching, and unadjusted spot market prices. This architecture created several vulnerabilities:
1. **Uncertainty Blindness:** Inability to anticipate shop unlocks occurring every 3 days, leading to sub-optimal crop selection.
2. **Calendar Rigidness:** Hardcoded day cutoffs (e.g. Melon cutoff on Day 18) prematurely halted high-value planting even when market demand and remaining maturity time made crops highly lucrative.
3. **Opponent Monopolization:** Susceptibility to opponent livestock expansions flooding specific product markets (Milk or Wool).

## Decision

We introduced **Leader V11 (Hybrid Engine)**, combining four complementary decision modules:

1. **Analytical Monte Carlo Price Oracle (`agent/domain/monte_carlo.py`):**
   Uses an $O(1)$ closed-form interval drain algorithm (`_analytical_drain`) and vectorized NumPy array operations to project expected prices at harvest time across 150 sampled shop unlock scenarios in $< 0.5$ms per turn.

2. **Dynamic Viability over Static Cutoffs (`agent/engines/leader_v11.py`):**
   Eliminates all static calendar cutoffs. Replaces them with exact physical maturity deadlines ($\text{day} + \text{maturity} \le 30$) and harvest-day price projections from the Monte Carlo Oracle.

3. **Real-time Opponent Tracker & Arbitrage (`agent/domain/opponent_model.py`):**
   Monitors opponent livestock and crop counts in real-time. Automatically pivots animal purchases (Cows vs. Sheep vs. Geese) to exploit unserved market demand.

4. **Hungarian Spatial Planner (`agent/engines/spatial_planner.py`):**
   Replaces combinatorial matching with $O(N^3)$ `scipy.optimize.linear_sum_assignment` for optimal multi-worker task assignment.

5. **Offline State Value Function (`agent/domain/value_function.py`):**
   Extracts 34 normalized state features and evaluates game states using a `HistGradientBoostingRegressor` trained on 100 self-play episodes ($R^2 = 0.175$, MAE = $\$3,476.90$). Bundled as a $< 160$KB `joblib` model binary.

## Consequences

- **Performance Milestones:** Achieved **94.0%** win rate vs LEADER-V7, **95.0%** vs LEADER-V8, **70.0%** vs LEADER-V9, and **65.0%** vs LEADER-V9-1 across 400 benchmark matches with positive net financial margin in 100% of matchups.
- **Kaggle Compliance:** Zero non-standard runtime dependencies. Package archive `dist/kaggriculture-submission.tar.gz` remains under 200KB and validates in isolated 720-turn episode execution.
