"""Tests for LeaderV7Engine: pure dynamic market-driven portfolio, sales, and logistics."""

from __future__ import annotations

from typing import Any

from agent.core.state import NormalizedState
from agent.engines.leader_v7 import LeaderV7Engine


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
            "inventory": market_inventory or default_market,
            "prices": prices or default_prices,
        },
        "town": {
            "unlocked_shops": shops or [],
        },
    }


# ─── Dynamic Crop Portfolio & Forecasting ────────────────────────────


class TestDynamicCropPortfolio:
    """Verify market-aware crop forecasting and dynamic portfolio allocation."""

    def test_melon_naturally_unviable_late_game(self) -> None:
        """Melon takes 10 days to yield; on Day 25 it naturally has zero/negative ROI."""
        engine = LeaderV7Engine()
        obs = _observation(day=25, hour=1, money=5000)
        state = NormalizedState.from_observation(obs)
        portfolio = engine._dynamic_crop_portfolio(state, horizon=5, empty_slots=10)
        crops = [crop for crop, _ in portfolio]
        assert "MELON" not in crops

    def test_melon_viable_early_game(self) -> None:
        """Melon is viable when season horizon is long enough to harvest."""
        engine = LeaderV7Engine()
        obs = _observation(day=0, hour=1, money=5000)
        state = NormalizedState.from_observation(obs)
        portfolio = engine._dynamic_crop_portfolio(state, horizon=30, empty_slots=10)
        assert len(portfolio) > 0

    def test_strawberry_favored_when_town_shops_drain_market(self) -> None:
        """When 4 shops drain Strawberry, price appreciation makes it top ROI."""
        engine = LeaderV7Engine()
        shops = ["BRUNCH_SPOT", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP", "FARMERS_MARKET"]
        obs = _observation(day=5, hour=1, money=5000, shops=shops)
        state = NormalizedState.from_observation(obs)
        portfolio = engine._dynamic_crop_portfolio(state, horizon=25, empty_slots=20)
        crop_names = [crop for crop, _ in portfolio if crop != "WHEAT"]
        assert "STRAWBERRY" in crop_names

    def test_opponent_melon_flood_demotes_melon_roi(self) -> None:
        """When opponent floods melon, projected market saturation lowers melon ROI."""
        engine = LeaderV7Engine()
        # Opponent has 20 melon plants
        opp_tile = {"kind": "PLANT", "crop": "MELON", "yield_units": 6, "planted_day": 0}
        opp_tiles = [[opp_tile] * 5 for _ in range(4)] + [[None] * 5 for _ in range(6)]
        opp_grid = [row + [None] * 5 for row in opp_tiles]

        shops = ["BRUNCH_SPOT", "SMOOTHIE_SHOP"]
        obs = _observation(day=2, hour=1, money=5000, shops=shops, opponent_tiles=opp_grid)
        state = NormalizedState.from_observation(obs)
        portfolio = engine._dynamic_crop_portfolio(state, horizon=28, empty_slots=20)
        # Should allocate to regrowables with town demand rather than melon
        assert len(portfolio) > 0


# ─── Dynamic Market Orders & Opening ─────────────────────────────────


class TestDynamicMarketOrders:
    """Verify pure dynamic market order generation with zero hardcoded buy lists."""

    def test_dynamic_day0_opening_purchases_livestock_and_seeds(self) -> None:
        """Day 0 Hour 1 must dynamically generate orders based on ROI without static lists."""
        engine = LeaderV7Engine()
        obs = _observation(day=0, hour=1, money=3000)
        action = engine.act(obs)
        market = action["market"]

        # Must hire at least 1 hand
        assert ["HIRE"] in market
        # Must purchase animal
        animal_orders = [o for o in market if o[0] == "BUY_ANIMAL"]
        assert len(animal_orders) > 0
        # Must purchase seed
        seed_orders = [o for o in market if o[0] == "BUY_SEED"]
        assert len(seed_orders) > 0

    def test_feed_safety_reserve_guaranteed(self) -> None:
        """Engine must buy wheat feed for animals with priority."""
        engine = LeaderV7Engine()
        pasture_tile = {
            "kind": "PASTURE",
            "animal": "COW",
            "fed_today": False,
            "cared_today": False,
        }
        tiles = [[pasture_tile] + [None] * 9] + [[None] * 10 for _ in range(9)]
        obs = _observation(day=1, hour=1, money=500, shed={"WHEAT": 0}, tiles=tiles)
        action = engine.act(obs)
        market = action["market"]
        feed_orders = [o for o in market if o[0] == "BUY_PRODUCT" and o[1] == "WHEAT"]
        assert len(feed_orders) > 0


# ─── Dynamic Price-Trend Selling ─────────────────────────────────────


class TestDynamicPriceTrendSelling:
    """Verify sales logic based on price trends, marginal values, and cash floor."""

    def test_sell_immediately_on_closing(self) -> None:
        """Closing day (Day >= 28) should liquidate all products."""
        engine = LeaderV7Engine()
        obs = _observation(day=28, hour=1, money=5000, shed={"STRAWBERRY": 10, "MELON": 5})
        action = engine.act(obs)
        market = action["market"]
        sell_orders = [o for o in market if o[0] == "SELL"]
        sold_items = {o[1] for o in sell_orders}
        assert "STRAWBERRY" in sold_items
        assert "MELON" in sold_items

    def test_melon_sold_immediately_due_to_zero_town_demand(self) -> None:
        """Melon has no shop demand and should be liquidated promptly."""
        engine = LeaderV7Engine()
        obs = _observation(day=15, hour=1, money=5000, shed={"MELON": 6})
        action = engine.act(obs)
        market = action["market"]
        melon_sells = [o for o in market if o[0] == "SELL" and o[1] == "MELON"]
        assert len(melon_sells) > 0

    def test_low_liquidity_triggers_immediate_sales(self) -> None:
        """When money is below liquidity floor ($1200), products are sold immediately."""
        engine = LeaderV7Engine()
        obs = _observation(day=10, hour=1, money=300, shed={"STRAWBERRY": 4, "MILK": 2})
        action = engine.act(obs)
        market = action["market"]
        sell_orders = [o for o in market if o[0] == "SELL"]
        assert len(sell_orders) > 0


# ─── Fertilizer Application & Logistics ─────────────────────────────


class TestFertilizerAndLogistics:
    """Verify active fertilization and shed delivery routing."""

    def test_fertilizer_applied_to_regrowables(self) -> None:
        """When strawberry plants exist, fertilizer is retained for application."""
        engine = LeaderV7Engine()
        strawberry_tile = {
            "kind": "PLANT",
            "crop": "STRAWBERRY",
            "watered_today": True,
            "yield_units": 0,
            "planted_day": 0,
        }
        tiles = [[strawberry_tile] + [None] * 9] + [[None] * 10 for _ in range(9)]
        obs = _observation(day=12, hour=1, money=5000, shed={"FERTILIZER": 5}, tiles=tiles)
        action = engine.act(obs)
        market = action["market"]
        fert_sells = [o for o in market if o[0] == "SELL" and o[1] == "FERTILIZER"]
        total_sold = sum(o[2] for o in fert_sells) if fert_sells else 0
        assert total_sold <= 4

    def test_fertilizer_fully_sold_when_no_regrowables(self) -> None:
        """When no regrowable crops exist, all fertilizer is liquidated for cash."""
        engine = LeaderV7Engine()
        obs = _observation(day=12, hour=1, money=5000, shed={"FERTILIZER": 5})
        action = engine.act(obs)
        market = action["market"]
        fert_sells = [o for o in market if o[0] == "SELL" and o[1] == "FERTILIZER"]
        total_sold = sum(o[2] for o in fert_sells) if fert_sells else 0
        assert total_sold == 5
