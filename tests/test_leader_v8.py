"""Tests for LeaderV8Engine: pure dynamic market-simulation, marginal ROI, and shop-aware livestock."""

from __future__ import annotations

from typing import Any

from agent.core.state import NormalizedState
from agent.engines.leader_v8 import LeaderV8Engine


def _observation(
    *,
    day: int = 0,
    hour: int = 0,
    money: int = 3000,
    shed: dict[str, int] | None = None,
    seeds: dict[str, int] | None = None,
    inventory: dict[str, int] | None = None,
    unit_inventories: list[dict[str, int]] | None = None,
    farmer_pos: tuple[int, int] = (4, 4),
    hands_pos: list[tuple[int, int]] | None = None,
    prices: dict[str, int] | None = None,
    market_inventory: dict[str, int] | None = None,
    shops: list[str] | None = None,
    tiles: list[list[dict[str, Any] | None]] | None = None,
    opponent_tiles: list[list[dict[str, Any] | None]] | None = None,
) -> dict[str, Any]:
    default_prices = {
        "WHEAT": 25,
        "CARROT": 35,
        "TOMATO": 60,
        "STRAWBERRY": 120,
        "MELON": 250,
        "EGG": 50,
        "MILK": 160,
        "WOOL": 200,
        "FERTILIZER": 100,
    }
    default_market = {k: 10_000 for k in default_prices}
    final_market = dict(default_market)
    if market_inventory:
        final_market.update(market_inventory)
    if unit_inventories is None:
        unit_inventories = [inventory or {}]

    if tiles is None:
        flat_tiles = [[None] * 10 for _ in range(10)]
    else:
        flat_tiles = tiles

    opp_flat_tiles = opponent_tiles or [[None] * 10 for _ in range(10)]

    return {
        "player": 0,
        "day": day,
        "hour": hour,
        "step": day * 24 + hour,
        "farms": [
            {
                "money": money,
                "farmer": list(farmer_pos),
                "hands": [list(h) for h in (hands_pos or [])],
                "tiles": flat_tiles,
            },
            {
                "money": 3000,
                "farmer": [14, 14],
                "hands": [],
                "tiles": opp_flat_tiles,
            },
        ],
        "private": {
            "shed": shed or {},
            "seeds": seeds or {},
            "inventories": unit_inventories,
        },
        "market": {
            "inventory": final_market,
            "prices": prices or default_prices,
        },
        "town": {
            "unlocked_shops": shops or [],
        },
    }


class TestLeaderV8PureDynamicOptimizer:
    """Verify pure dynamic tile-by-tile marginal ROI optimization without static caps."""

    def test_dynamic_crop_portfolio_allocates_high_roi_crops(self) -> None:
        """Dynamic portfolio should allocate high ROI crops without requiring hardcoded limits."""
        engine = LeaderV8Engine()
        obs = _observation(day=1, hour=1, money=5000)
        state = NormalizedState.from_observation(obs)
        portfolio = engine._dynamic_crop_portfolio(state, horizon=29, empty_slots=20)
        assert len(portfolio) > 0
        total_allocated = sum(qty for _, qty in portfolio)
        assert total_allocated > 0

    def test_melon_allocation_naturally_throttled_by_marginal_decay(self) -> None:
        """When market melon inventory is flooded, marginal ROI forces optimizer to choose non-melon crops."""
        engine = LeaderV8Engine()
        market_inv = {"MELON": 10_150}
        obs = _observation(day=2, hour=1, money=5000, market_inventory=market_inv)
        state = NormalizedState.from_observation(obs)
        portfolio = engine._dynamic_crop_portfolio(state, horizon=28, empty_slots=20)
        crops = [crop for crop, _ in portfolio if crop != "WHEAT"]
        assert "MELON" not in crops

    def test_strawberry_favored_when_town_shops_demand_strawberry(self) -> None:
        """When town shops drain strawberry and livestock generates fertilizer, marginal simulation shifts allocation to Strawberry."""
        engine = LeaderV8Engine()
        shops = ["BRUNCH_SPOT", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP", "FARMERS_MARKET"]
        pasture_tile = {"kind": "PASTURE", "animal": "COW", "fed_today": True}
        tiles = [[pasture_tile] + [None] * 9] + [[None] * 10 for _ in range(9)]
        obs = _observation(day=5, hour=1, money=5000, shops=shops, tiles=tiles)
        state = NormalizedState.from_observation(obs)
        portfolio = engine._dynamic_crop_portfolio(state, horizon=25, empty_slots=20)
        crop_names = [crop for crop, _ in portfolio]
        assert "STRAWBERRY" in crop_names


class TestLeaderV8ShopAwareness:
    """Verify shop-aware livestock selection and sales execution."""

    def test_cows_favored_over_sheep_when_no_yarn_store(self) -> None:
        """Without Yarn Store, livestock expansion favors Cows to capture Dairy shop demand."""
        engine = LeaderV8Engine()
        shops = ["PIZZA_SHOP", "ICE_CREAM_SHOP"]
        pasture_tile = {"kind": "PASTURE", "animal": None}
        tiles = [[pasture_tile] + [None] * 9] + [[None] * 10 for _ in range(9)]
        obs = _observation(day=4, hour=1, money=5000, shops=shops, tiles=tiles)
        action = engine.act(obs)
        market = action["market"]
        animal_buys = [o for o in market if o[0] == "BUY_ANIMAL"]
        if animal_buys:
            assert animal_buys[0][1] == "COW"
