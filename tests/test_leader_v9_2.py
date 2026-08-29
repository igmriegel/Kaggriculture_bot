"""Tests for LeaderV92Engine: calibrated crop ROI logic, crop cutoffs, and adaptive Day 0 opening.
"""

from __future__ import annotations

from typing import Any

from agent.core.state import NormalizedState
from agent.engines.leader_v9_1 import LeaderV91Engine
from agent.engines.leader_v9_2 import LeaderV92Engine


def _observation(
    *,
    day: int = 0,
    hour: int = 0,
    money: int = 3000,
    market_inventory: dict[str, int] | None = None,
    prices: dict[str, int] | None = None,
    shops: list[str] | None = None,
    tiles: list[list[dict[str, Any] | None]] | None = None,
) -> dict[str, Any]:
    base_inv = {
        "WHEAT": 10000,
        "CARROT": 10000,
        "TOMATO": 10000,
        "STRAWBERRY": 10000,
        "MELON": 10000,
        "MILK": 10000,
        "WOOL": 10000,
        "EGG": 10000,
        "FERTILIZER": 10000,
    }
    if market_inventory:
        base_inv.update(market_inventory)

    base_prices = {
        "WHEAT": 25,
        "CARROT": 35,
        "TOMATO": 60,
        "STRAWBERRY": 120,
        "MELON": 250,
        "MILK": 160,
        "WOOL": 200,
        "EGG": 50,
        "FERTILIZER": 100,
    }
    if prices:
        base_prices.update(prices)

    if tiles is None:
        tiles = [[None] * 10 for _ in range(10)]

    return {
        "day": day,
        "hour": hour,
        "step": day * 24 + hour,
        "player": 0,
        "remainingOverageTime": 60.0,
        "farms": [
            {
                "farmer": [4, 4],
                "hands": [],
                "hires_today": 0,
                "money": float(money),
                "tiles": tiles,
                "unlocked_quadrants": ["NW"],
            },
            {
                "farmer": [4, 4],
                "hands": [],
                "hires_today": 0,
                "money": 3000.0,
                "tiles": [[None] * 10 for _ in range(10)],
                "unlocked_quadrants": ["NW"],
            },
        ],
        "market": {"inventory": base_inv, "prices": base_prices},
        "town": {"unlocked_shops": shops or []},
        "private": {
            "shed": {
                "WHEAT": 10,
                "CARROT": 0,
                "TOMATO": 0,
                "STRAWBERRY": 0,
                "MELON": 0,
                "MILK": 0,
                "WOOL": 0,
                "EGG": 0,
                "FERTILIZER": 5,
            },
        },
    }


class TestLeaderV92Engine:
    def test_day_0_hour_1_adaptive_opening_no_strawberry_shop(self) -> None:
        """Step 1 (Day 0, Hour 1) buys Melon seeds when no Strawberry shop is present."""
        engine = LeaderV92Engine()
        obs = _observation(day=0, hour=1, money=3000, shops=["BAKERY", "PIZZA_SHOP"])
        obs["private"]["shed"] = {k: 0 for k in obs["private"]["shed"]}
        state = NormalizedState.from_observation(obs)
        orders = engine._build_market_orders(state, (), [])
        assert len(orders) == 6
        assert orders[0] == ["HIRE"]
        assert orders[1] == ["HIRE"]
        assert orders[2] == ["BUY_ANIMAL", "COW", 2]
        assert orders[3] == ["BUY_ANIMAL", "SHEEP", 2]
        assert orders[4] == ["BUY_SEED", "MELON", 4]
        assert orders[5] == ["BUY_SEED", "WHEAT", 6]

    def test_day_0_hour_1_adaptive_opening_with_strawberry_shop(self) -> None:
        """Step 1 (Day 0, Hour 1) buys Strawberry seeds when Strawberry shop is present."""
        engine = LeaderV92Engine()
        obs = _observation(day=0, hour=1, money=3000, shops=["BRUNCH_SPOT"])
        obs["private"]["shed"] = {k: 0 for k in obs["private"]["shed"]}
        state = NormalizedState.from_observation(obs)
        orders = engine._build_market_orders(state, (), [])
        assert len(orders) == 6
        assert orders[4] == ["BUY_SEED", "STRAWBERRY", 3]
        assert orders[5] == ["BUY_SEED", "WHEAT", 6]

    def test_wheat_penalty_calibrated(self) -> None:
        """WHEAT has a penalty of exactly -12.0 in V9.2 vs -1.5 in V9.1."""
        engine_v9_1 = LeaderV91Engine()
        engine_v9_2 = LeaderV92Engine()
        obs = _observation(day=6, hour=1, money=4000)
        state = NormalizedState.from_observation(obs)

        roi_v9_1 = engine_v9_1._calculate_marginal_tile_roi(
            "WHEAT", state, horizon=24, current_planned_tiles=0
        )
        roi_v9_2 = engine_v9_2._calculate_marginal_tile_roi(
            "WHEAT", state, horizon=24, current_planned_tiles=0
        )
        # The penalty difference between V9.1 and V9.2 should be exactly 10.5
        assert roi_v9_1 - roi_v9_2 == 10.5

    def test_melon_cutoff_day_12(self) -> None:
        """MELON ROI is positive on day 11, but drops to 0.0 on day 13."""
        engine = LeaderV92Engine()

        obs_d11 = _observation(day=11, hour=1, money=4000)
        state_d11 = NormalizedState.from_observation(obs_d11)
        roi_d11 = engine._calculate_marginal_tile_roi(
            "MELON", state_d11, horizon=19, current_planned_tiles=0
        )
        assert roi_d11 > 0.0

        obs_d13 = _observation(day=13, hour=1, money=4000)
        state_d13 = NormalizedState.from_observation(obs_d13)
        roi_d13 = engine._calculate_marginal_tile_roi(
            "MELON", state_d13, horizon=17, current_planned_tiles=0
        )
        assert roi_d13 == 0.0
