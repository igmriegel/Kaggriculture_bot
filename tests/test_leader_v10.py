"""Tests for LeaderV10Engine: livestock prioritization, smart watering, and egg synergy."""

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
    shops: list[str] | None = None,
    tiles: list[list[dict[str, Any] | None]] | None = None,
    shed: dict[str, int] | None = None,
) -> dict[str, Any]:
    base_shed = {
        "WHEAT": 10,
        "CARROT": 0,
        "TOMATO": 0,
        "STRAWBERRY": 0,
        "MELON": 0,
        "MILK": 0,
        "WOOL": 0,
        "EGG": 0,
        "FERTILIZER": 5,
    }
    if shed:
        base_shed.update(shed)
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
            "shed": base_shed,
            "seeds": {"WHEAT": 0, "CARROT": 0, "TOMATO": 0, "STRAWBERRY": 0, "MELON": 0},
            "inventories": [{}],
        },
        "town": {"unlocked_shops": shops or []},
    }


class TestLeaderV10Engine:
    def test_wheat_crop_suppressed_after_day_one(self) -> None:
        """From Day 2 onwards, wheat seeds are not planned for planting."""
        engine = LeaderV10Engine()
        obs = _observation(day=2, hour=1, money=4000)
        state = NormalizedState.from_observation(obs)
        portfolio = engine._dynamic_crop_portfolio(state, horizon=28, empty_slots=5)
        crops = [c for c, _ in portfolio]
        assert "WHEAT" not in crops

    def test_smart_watering_suppresses_useless_watering(self) -> None:
        """Watering is suppressed for crops that cannot mature before Day 30."""
        engine = LeaderV10Engine()
        # Melon planted on Day 28 takes 6 days to mature. Won't harvest before Day 30.
        melon_tile = {
            "kind": "PLANT",
            "crop": "MELON",
            "planted_day": 28,
            "watered_today": False,
            "consecutive_unwatered": 0,
            "yield_units": 0,
        }
        tiles = [[melon_tile] + [None] * 9] + [[None] * 10 for _ in range(9)]
        obs = _observation(day=28, hour=2, money=2000, tiles=tiles)
        state = NormalizedState.from_observation(obs)
        goals = engine._goals(state)
        tasks = engine._tasks(state, goals)
        water_tasks = [t for t in tasks if "WATER" in t.command]
        assert len(water_tasks) == 0

    def test_multiple_animal_buying_on_high_liquidity(self) -> None:
        """When cash is high, up to 2 animals are bought in the same turn."""
        engine = LeaderV10Engine()
        pasture_tile = {"kind": "PASTURE", "animal": None}
        tiles = [[pasture_tile] + [None] * 9] + [[None] * 10 for _ in range(9)]
        # Having $6000 and target_animals > current_animals trigger double buy
        obs = _observation(day=5, hour=1, money=6000, tiles=tiles)
        state = NormalizedState.from_observation(obs)
        goals = engine._goals(state)
        orders = engine._build_market_orders(state, goals, [])
        buy_animal_orders = [o for o in orders if o[0] == "BUY_ANIMAL"]
        assert len(buy_animal_orders) > 0
        assert buy_animal_orders[0][2] == 2

    def test_delay_livestock_buying_when_melons_are_dirt_cheap(self) -> None:
        """On day 1, if melon seed price is extremely cheap, livestock purchase is delayed."""
        engine = LeaderV10Engine()
        pasture_tile = {"kind": "PASTURE", "animal": None}
        tiles = [[pasture_tile] + [None] * 9] + [[None] * 10 for _ in range(9)]
        obs = _observation(day=1, hour=1, money=4000, prices={"MELON": 50}, tiles=tiles)
        state = NormalizedState.from_observation(obs)
        goals = engine._goals(state)
        orders = engine._build_market_orders(state, goals, [])
        buy_seeds = [o for o in orders if o[0] == "BUY_SEED"]
        assert len(buy_seeds) > 0

    def test_prioritize_livestock_buying_when_no_deals(self) -> None:
        """On day 1, if crop seed prices are normal/high, livestock is prioritized first."""
        engine = LeaderV10Engine()
        pasture_tile = {"kind": "PASTURE", "animal": None}
        tiles = [[pasture_tile] + [None] * 9] + [[None] * 10 for _ in range(9)]
        obs = _observation(
            day=1, hour=1, money=4000, prices={"MELON": 250, "STRAWBERRY": 120}, tiles=tiles
        )
        state = NormalizedState.from_observation(obs)
        goals = engine._goals(state)
        orders = engine._build_market_orders(state, goals, [])
        buy_animal = [o for o in orders if o[0] == "BUY_ANIMAL"]
        assert len(buy_animal) > 0

    def test_market_speculation_holds_on_low_price(self) -> None:
        """Shed inventory is not sold when current crop price is deflated compared to projection."""
        engine = LeaderV10Engine()
        # MELON current price is $70, expected/projected is $150.
        # Hold threshold is 0.85, so 70 < 150 * 0.85 is True.
        # Cash is $2000 (above min liquidity of 1500).
        # It should NOT generate a SELL order for MELON.
        obs = _observation(
            day=10, 
            hour=1, 
            money=2000, 
            prices={"MELON": 70}, 
            shed={"MELON": 5}
        )
        state = NormalizedState.from_observation(obs)
        projected = {"MELON": 150}
        sales = engine._sales(state, projected)
        assert len([s for s in sales if s[0] == "SELL" and s[1] == "MELON"]) == 0

        # Conversely, if we have low cash ($500 < $1500), it should ignore speculation
        # and SELL to get cash.
        obs_low_cash = _observation(
            day=10, 
            hour=1, 
            money=500, 
            prices={"MELON": 70}, 
            shed={"MELON": 5}
        )
        state_low_cash = NormalizedState.from_observation(obs_low_cash)
        sales_low_cash = engine._sales(state_low_cash, projected)
        assert len([s for s in sales_low_cash if s[0] == "SELL" and s[1] == "MELON"]) > 0
