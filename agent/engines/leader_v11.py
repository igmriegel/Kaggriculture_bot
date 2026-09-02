"""Leader V11: Hybrid Engine with Monte Carlo Price Oracle & Opponent Tracker.

Key Innovations:
1. Monte Carlo Price Oracle: Simulates market price distributions (mean, p10, p90)
   under shop unlock uncertainty to refine crop ROI and holding decisions.
2. Opponent Behavioral Tracker: Tracks real-time opponent planting/harvesting patterns
   and predicts market supply dumps dynamically.
3. Tactical Worker Lookahead: Scipy Hungarian bipartite assignment with route optimization.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent.core.state import NormalizedState
from agent.domain.monte_carlo import monte_carlo_price_projection
from agent.domain.opponent_model import OpponentTracker
from agent.engines.leader_v9_2 import LeaderV92Config, LeaderV92Engine


@dataclass(frozen=True)
class LeaderV11Config(LeaderV92Config):
    mc_samples: int = 150
    mc_weight: float = 0.0503
    wheat_labor_penalty: float = 5.02
    carrot_labor_penalty: float = 3.50
    carrot_late_penalty: float = 2.19
    min_cash_buffer_livestock: int = 730
    double_animal_buy_threshold: int = 1264


class LeaderV11Engine(LeaderV92Engine):
    """Eleventh Generation Hybrid Engine (V11)."""

    def __init__(self, config: LeaderV11Config | None = None) -> None:
        self.v11_config = config or LeaderV11Config()
        super().__init__(self.v11_config)
        self.opp_tracker = OpponentTracker()
        self._mc_cache: dict[str, tuple[float, float, float]] | None = None

    def reset_cycle(self) -> None:
        super().reset_cycle()
        self.opp_tracker.reset()
        self._mc_cache = None

    def act(self, observation: dict[str, Any]) -> dict[str, Any]:
        # Track opponent behavior on each turn
        state = NormalizedState.from_observation(observation)
        self.opp_tracker.update(state)
        self._mc_cache = None  # Reset MC cache per turn
        return super().act(observation)

    def _get_mc_prices(
        self, state: NormalizedState, target_day: int
    ) -> dict[str, tuple[float, float, float]]:
        if self._mc_cache is None:
            self._mc_cache = monte_carlo_price_projection(
                state.market_inventory,
                state.shops,
                state.day,
                state.hour,
                target_day,
                n_samples=self.v11_config.mc_samples,
            )
        return self._mc_cache

    def _calculate_marginal_tile_roi(
        self, crop: str, state: NormalizedState, horizon: int, current_planned_tiles: int
    ) -> float:
        # 1. Base ROI from V8 (bypassing V92 static day cutoffs)
        from agent.engines.leader_v9 import LeaderV9Engine

        base_roi = super(LeaderV9Engine, self)._calculate_marginal_tile_roi(
            crop, state, horizon, current_planned_tiles
        )

        cfg = self.v11_config

        # 2. Labor Friction Penalties
        if crop == "WHEAT":
            return max(0.0, base_roi - cfg.wheat_labor_penalty)
        elif crop == "CARROT":
            penalty = cfg.carrot_late_penalty if state.day > 16 else cfg.carrot_labor_penalty
            return max(0.0, base_roi - penalty)

        # 3. Dynamic Melon Viability (100% Market & Maturity Driven - NO static day cutoff!)
        if crop == "MELON":
            maturity_day = state.day + 10
            if maturity_day > 30:
                return 0.0  # Physical impossibility: cannot mature before Day 30
            roi = base_roi * 1.3
            if state.day > 15:
                mc_prices = self._get_mc_prices(state, maturity_day)
                mc_mean = mc_prices.get("MELON", (0.0, 0.0, 0.0))[0]
                spot_price = state.prices.get("MELON", 0)
                if mc_mean < 140.0 and spot_price < 170.0:
                    return 0.0
            return roi

        # 4. Dynamic Strawberry Viability (100% Market & Maturity Driven - NO static day cutoff!)
        if crop == "STRAWBERRY":
            first_harvest_day = state.day + 4
            if first_harvest_day > 30:
                return 0.0  # Physical impossibility: cannot yield 1st harvest before Day 30
            roi = base_roi * (1.5 if state.day < 12 else 1.25)
            if state.day > 18:
                mc_prices = self._get_mc_prices(state, first_harvest_day)
                mc_mean = mc_prices.get("STRAWBERRY", (0.0, 0.0, 0.0))[0]
                spot_price = state.prices.get("STRAWBERRY", 0)
                if mc_mean < 75.0 and spot_price < 95.0:
                    return 0.0
            return roi

        if base_roi <= 0.0:
            return 0.0

        # 5. Monte Carlo Price Adjustment for remaining crops
        from agent.domain.roi import CROPS_SPEC

        spec = CROPS_SPEC.get(crop, {})
        first_yield_day = int(spec.get("first_yield_day", 2))
        harvest_day = min(30, state.day + first_yield_day)

        mc_prices = self._get_mc_prices(state, harvest_day)
        if crop in mc_prices and crop in state.prices:
            mc_mean, _mc_p10, _mc_p90 = mc_prices[crop]
            spot_price = state.prices[crop]

            if spot_price > 0:
                blended_price = (
                    1.0 - cfg.mc_weight
                ) * spot_price + cfg.mc_weight * mc_mean
                adjustment = blended_price / spot_price
                base_roi *= min(1.2, max(0.8, adjustment))

        return base_roi
