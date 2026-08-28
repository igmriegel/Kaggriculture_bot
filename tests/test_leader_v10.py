"""Tests for LeaderV10Engine: spatial zoning, feed sourcing and late clearance."""

from __future__ import annotations

from typing import Any

from agent.core.state import NormalizedState
from agent.engines.leader_v10 import LeaderV10Engine


def _observation(
    *,
    day: int = 0,
    hour: int = 0,
    money: int = 3000,
    market_inventory: dict[str, int] | None = None,
    prices: dict[str, int] | None = None,
    tiles: list[list[dict[str, Any] | None]] | None = None,
    shed: dict[str, int] | None = None,
) -> dict[str, Any]:
    base_inv = {
        "WHEAT": 10000,
        "CARROT": 10000,
        "TOMATO": 10000,
        "STRAWBERRY": 10000,
        "MELON": 10000,
        "MILK": 10000,
        "WOOL": 10000,
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
        "FERTILIZER": 100,
    }
    if prices:
        base_prices.update(prices)

    if tiles is None:
        tiles = [[None] * 10 for _ in range(10)]

    base_shed = {
        "WHEAT": 10,
        "CARROT": 0,
        "TOMATO": 0,
        "STRAWBERRY": 0,
        "MELON": 0,
        "MILK": 0,
        "WOOL": 0,
        "FERTILIZER": 5,
    }
    if shed:
        base_shed.update(shed)

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
            "shed": base_shed,
            "seeds": {"WHEAT": 0, "CARROT": 0, "TOMATO": 0, "STRAWBERRY": 0, "MELON": 0},
            "inventories": [{}],
        },
        "town": {"unlocked_shops": []},
    }


class TestLeaderV10Engine:
    def test_feed_sourcing_blocks_wheat_planting_on_low_price(self) -> None:
        """When Wheat price is low (< $35), it is excluded from dynamic crop portfolio."""
        engine = LeaderV10Engine()
        obs = _observation(day=5, hour=1, money=4000, prices={"WHEAT": 20})
        state = NormalizedState.from_observation(obs)
        portfolio = engine._dynamic_crop_portfolio(state, horizon=20, empty_slots=10)
        crops = [crop for crop, _ in portfolio]
        assert "WHEAT" not in crops

    def test_livestock_late_game_clearance_sells_on_day_29(self) -> None:
        """On day 29, active animals are sold back to the market."""
        engine = LeaderV10Engine()
        tiles = [[None] * 10 for _ in range(10)]
        tiles[0][0] = {"kind": "PASTURE", "animal": "COW", "fed_today": True}
        obs = _observation(day=29, hour=1, money=4000, tiles=tiles)
        state = NormalizedState.from_observation(obs)
        goals = engine._goals(state)
        orders = engine._build_market_orders(state, goals, [])
        sell_cows = [o for o in orders if o[0] == "SELL" and o[1] == "COW"]
        assert len(sell_cows) > 0

    def test_zoning_prioritizes_periphery_for_planting(self) -> None:
        """Planting tasks prefer tiles furthest away from the central Shed (Manhattan distance)."""
        engine = LeaderV10Engine()
        # Plant WHEAT task
        obs = _observation(day=5, hour=1, money=4000)
        obs["private"]["seeds"]["WHEAT"] = 1
        state = NormalizedState.from_observation(obs)
        goals = engine._goals(state)
        tasks = engine._tasks(state, goals)
        plant_tasks = [t for t in tasks if t.command and t.command[0] == "PLANT"]
        assert len(plant_tasks) > 0
        # Target should not be close (like [4, 4] or [4, 5]) but peripheral (like [0, 0])
        # since we reversed the proximity sort list.
        target_x, target_y = plant_tasks[0].target
        dist_to_shed = abs(target_x - 4) + abs(target_y - 4)
        assert dist_to_shed > 1
