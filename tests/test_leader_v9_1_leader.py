"""Tests for LeaderV9_1LeaderEngine: opening book, bias, pivot, and sell-off."""

from __future__ import annotations

from typing import Any

from agent.core.state import NormalizedState
from agent.engines.leader_v9_1_leader import LeaderV9_1LeaderEngine


def _observation(
    *,
    day: int = 0,
    hour: int = 0,
    money: int = 3000,
    market_inventory: dict[str, int] | None = None,
    prices: dict[str, int] | None = None,
    shops: list[str] | None = None,
    tiles: list[list[dict[str, Any] | None]] | None = None,
    opp_tiles: list[list[dict[str, Any] | None]] | None = None,
    opp_hands: list[list[int]] | None = None,
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
    if opp_tiles is None:
        opp_tiles = [[None] * 10 for _ in range(10)]

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
                "unlocked_quadrants": ["NW", "NE", "SW"],
            },
            {
                "farmer": [4, 4],
                "hands": opp_hands or [],
                "hires_today": len(opp_hands) if opp_hands else 0,
                "money": 3000.0,
                "tiles": opp_tiles,
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


class TestLeaderV9_1LeaderEngine:
    def test_day_zero_opening_book(self) -> None:
        """Day 0 must use Crop Dusta's exact deterministic opening book orders."""
        engine = LeaderV9_1LeaderEngine()

        # Day 0 Hour 1
        obs = _observation(day=0, hour=1)
        action = engine.act(obs)
        assert action["market"] == [
            ["HIRE"],
            ["HIRE"],
            ["HIRE"],
            ["HIRE"],
            ["BUY_ANIMAL", "COW", 2],
            ["BUY_ANIMAL", "SHEEP", 2],
            ["BUY_SEED", "STRAWBERRY", 3],
            ["BUY_SEED", "WHEAT", 15],
        ]

        # Day 0 Hour 2
        obs = _observation(day=0, hour=2)
        action = engine.act(obs)
        assert action["market"] == [
            ["BUY_PRODUCT", "WHEAT", 4],
            ["BUY_ANIMAL", "COW", 1],
        ]

        # Day 0 Hour 3
        obs = _observation(day=0, hour=3)
        action = engine.act(obs)
        assert action["market"] == [
            ["BUY_PRODUCT", "WHEAT", 4],
        ]

    def test_dynamic_wheat_bias_opp_tiles(self) -> None:
        """Wheat bias is reduced to 1.0 if the opponent has >= 5 wheat tiles."""
        engine = LeaderV9_1LeaderEngine()

        # Opponent has 5 wheat tiles
        opp_tiles = [[None] * 10 for _ in range(10)]
        for i in range(5):
            opp_tiles[0][i] = {"kind": "PLANT", "crop": "WHEAT", "watered_today": True}

        obs = _observation(day=5, hour=1, opp_tiles=opp_tiles)
        state = NormalizedState.from_observation(obs)

        roi_with_opp_wheat = engine._calculate_marginal_tile_roi("WHEAT", state, 25, 0)

        # Opponent has 0 wheat tiles
        obs_no_opp = _observation(day=5, hour=1)
        state_no_opp = NormalizedState.from_observation(obs_no_opp)
        roi_no_opp = engine._calculate_marginal_tile_roi("WHEAT", state_no_opp, 25, 0)

        # ROI should be lower when opponent has wheat tiles (since bias is 1.0 vs 1.2)
        assert roi_with_opp_wheat < roi_no_opp

    def test_shop_aware_carrot_pivot(self) -> None:
        """Carrot ROI is boosted after Day 20 only if carrot-accepting shops are open."""
        engine = LeaderV9_1LeaderEngine()

        # Day 21 with PET_CAFE shop (accepts CARROT)
        obs_with_shop = _observation(day=21, hour=1, shops=["PET_CAFE"])
        state_with_shop = NormalizedState.from_observation(obs_with_shop)
        roi_with_shop = engine._calculate_marginal_tile_roi("CARROT", state_with_shop, 9, 0)

        # Day 21 with no carrot shops
        obs_no_shop = _observation(day=21, hour=1, shops=["YARN_STORE"])
        state_no_shop = NormalizedState.from_observation(obs_no_shop)
        roi_no_shop = engine._calculate_marginal_tile_roi("CARROT", state_no_shop, 9, 0)

        assert roi_with_shop > roi_no_shop

    def test_day_29_sell_off(self) -> None:
        """Day 29 must initiate complete sell-off and issue zero planting/purchase commands."""
        engine = LeaderV9_1LeaderEngine()
        obs = _observation(day=29, hour=1)
        action = engine.act(obs)

        # Should only contain SELL orders from shed
        assert len(action["market"]) > 0
        assert all(order[0] == "SELL" for order in action["market"])

        # Tasks should not have PLANT or WATER commands
        assert not any(op in task for task in action["farmer"] for op in ("PLANT", "WATER"))
