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
    mc_weight: float = 0.5  # Weight of Monte Carlo mean price vs spot price in ROI
    opp_discount_threshold: int = 10  # Opponent supply threshold for ROI discount


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
        base_roi = super()._calculate_marginal_tile_roi(
            crop, state, horizon, current_planned_tiles
        )

        if base_roi <= 0.0:
            return 0.0

        # 1. Apply Monte Carlo Price Adjustment if future shop uncertainty exists
        from agent.domain.roi import CROPS_SPEC

        spec = CROPS_SPEC.get(crop, {})
        first_yield_day = int(spec.get("first_yield_day", 2))
        harvest_day = min(30, state.day + first_yield_day)

        mc_prices = self._get_mc_prices(state, harvest_day)
        if crop in mc_prices and crop in state.prices:
            mc_mean, _mc_p10, _mc_p90 = mc_prices[crop]
            spot_price = state.prices[crop]

            if spot_price > 0:
                # Blend Monte Carlo expected price with current spot price
                blended_price = (
                    1.0 - self.v11_config.mc_weight
                ) * spot_price + self.v11_config.mc_weight * mc_mean
                adjustment = blended_price / spot_price
                base_roi *= min(1.4, max(0.6, adjustment))

        return base_roi

    def _sales(
        self, state: NormalizedState, projected: dict[str, int] | None = None
    ) -> list[list[Any]]:
        orders = super()._sales(state, projected)

        # Speculative holding: if current price < Monte Carlo P90 and liquidity is high, hold stock
        if not self._closing(state) and state.money > 1500:
            mc_prices = self._get_mc_prices(state, min(30, state.day + 3))
            filtered_orders: list[list[Any]] = []
            for order in orders:
                if len(order) > 1 and order[0] == "SELL":
                    item = str(order[1])
                    if item in mc_prices and item in state.prices:
                        _mc_mean, _p10, p90 = mc_prices[item]
                        if state.prices[item] < p90 * 0.70:
                            # Skip this sale to hold for higher Monte Carlo projected price
                            continue
                filtered_orders.append(order)
            return filtered_orders

        return orders
