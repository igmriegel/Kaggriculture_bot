"""Tests for LeaderV91Engine: deterministic Crop Dusta opening and optimized crop ROI logic."""

from __future__ import annotations

from typing import Any

from agent.core.state import NormalizedState
from agent.engines.leader_v9 import LeaderV9Engine
from agent.engines.leader_v9_1 import LeaderV91Engine


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
            "seeds": {"WHEAT": 0, "CARROT": 0, "TOMATO": 0, "STRAWBERRY": 0, "MELON": 0},
            "inventories": [{}],
        },
        "town": {"unlocked_shops": shops or []},
    }


class TestLeaderV91Engine:
    def test_day_0_hour_1_opening_orders(self) -> None:
        """Step 1 (Day 0, Hour 1) must return the deterministic Crop Dusta opening book."""
        engine = LeaderV91Engine()
        obs = _observation(day=0, hour=1, money=3000)
        # Clear the shed to match real day 0 state where no animals exist yet
        obs["private"]["shed"] = {k: 0 for k in obs["private"]["shed"]}
        state = NormalizedState.from_observation(obs)
        orders = engine._build_market_orders(state, (), [])
        assert len(orders) == 8
        assert [o[0] for o in orders] == [
            "HIRE",
            "HIRE",
            "HIRE",
            "HIRE",
            "BUY_ANIMAL",
            "BUY_ANIMAL",
            "BUY_SEED",
            "BUY_SEED",
        ]

    def test_day_0_hour_2_opening_orders(self) -> None:
        """Step 2 (Day 0, Hour 2) must return cow and wheat feed orders."""
        engine = LeaderV91Engine()
        # Mocking 4 hands and 4 animals to match state representation after step 1
        obs = _observation(day=0, hour=2, money=700)
        obs["farms"][0]["hands"] = [[4, 4]] * 4
        obs["farms"][0]["tiles"][0][0] = {"kind": "PASTURE", "animal": "COW"}
        obs["farms"][0]["tiles"][0][1] = {"kind": "PASTURE", "animal": "COW"}
        obs["farms"][0]["tiles"][0][2] = {"kind": "PASTURE", "animal": "SHEEP"}
        obs["farms"][0]["tiles"][0][3] = {"kind": "PASTURE", "animal": "SHEEP"}

        state = NormalizedState.from_observation(obs)
        orders = engine._build_market_orders(state, (), [])
        assert len(orders) == 2
        assert orders[0] == ["BUY_PRODUCT", "WHEAT", 4]
        assert orders[1] == ["BUY_ANIMAL", "COW", 1]

    def test_crop_roi_wheat_not_penalized(self) -> None:
        """WHEAT has lower penalty in V9.1 than V9, resulting in higher ROI."""
        engine_v9 = LeaderV9Engine()
        engine_v9_1 = LeaderV91Engine()
        obs = _observation(day=6, hour=1, money=4000)
        state = NormalizedState.from_observation(obs)
        roi_v9 = engine_v9._calculate_marginal_tile_roi(
            "WHEAT", state, horizon=24, current_planned_tiles=0
        )
        roi_v9_1 = engine_v9_1._calculate_marginal_tile_roi(
            "WHEAT", state, horizon=24, current_planned_tiles=0
        )
        # The penalty reduction from 12.0 to 1.5 should increase ROI by exactly 10.5
        assert roi_v9_1 - roi_v9 == 10.5
