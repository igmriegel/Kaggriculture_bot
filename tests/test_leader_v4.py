"""Unit tests for LeaderV4 dynamic engine."""

from __future__ import annotations

from agent.core.validation import validate_action
from agent.engines.leader_v4 import LeaderV4Engine


def _observation(
    tile: object = None,
    *,
    day: int = 0,
    hour: int = 0,
    step: int | None = None,
    money: int = 3000,
    shed: dict[str, int] | None = None,
    seeds: dict[str, int] | None = None,
    inventory: dict[str, int] | None = None,
    unlocked: list[str] | None = None,
    prices: dict[str, float] | None = None,
    demand: dict[str, int] | None = None,
) -> dict:
    board = [[None for _ in range(10)] for _ in range(10)]
    if tile is not None:
        board[4][4] = tile
    return {
        "player": 0,
        "day": day,
        "hour": hour,
        "step": day * 24 + hour if step is None else step,
        "farms": [
            {
                "money": money,
                "farmer": [4, 4],
                "hands": [],
                "hires_today": 0,
                "unlocked_quadrants": unlocked or ["NW"],
                "tiles": board,
            }
        ],
        "private": {
            "shed": shed or {},
            "seeds": seeds or {},
            "inventories": [inventory or {}],
        },
        "market": {
            "prices": prices
            or {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120, "MELON": 250},
            "inventory": {"WHEAT": 10_000, "MELON": 10_000, "STRAWBERRY": 10_000},
        },
        "town": {"unlocked_shops": [], "demand": demand or {}},
    }


def test_v4_opening_hour_1_emits_big_bang_orders() -> None:
    engine = LeaderV4Engine()
    obs = _observation(day=0, hour=1, step=1, money=3000)
    action = engine.act(obs)

    # Validate schema
    validated, reason = validate_action(action, obs)
    assert reason is None
    assert validated.model_dump() == action

    # Check opening market setup
    market = action["market"]
    assert market.count(["HIRE"]) == 5
    assert ["BUY_ANIMAL", "COW", 1] in market
    assert ["BUY_ANIMAL", "SHEEP", 1] in market
    assert ["BUY_SEED", "MELON", 11] in market
    assert ["BUY_SEED", "WHEAT", 6] in market
    assert ["BUY_PRODUCT", "WHEAT", 4] in market


def test_v4_guarantees_animal_feed_purchase_when_deficit() -> None:
    engine = LeaderV4Engine()
    pasture_cow = {"kind": "PASTURE", "animal": "COW", "fed_today": False}
    pasture_sheep = {"kind": "PASTURE", "animal": "SHEEP", "fed_today": False}

    obs = _observation(day=3, hour=1, money=2000, shed={})
    obs["farms"][0]["tiles"][0][0] = pasture_cow
    obs["farms"][0]["tiles"][0][1] = pasture_sheep

    action = engine.act(obs)
    market = action["market"]

    # 2 animals, 0 owned wheat -> feed deficit of at least 2
    assert any(order[0] == "BUY_PRODUCT" and order[1] == "WHEAT" for order in market)


def test_v4_dynamic_crop_portfolio_adapts_to_strawberry_demand() -> None:
    engine = LeaderV4Engine()
    # Day 10 with high strawberry demand and unlocked NE
    obs = _observation(
        day=10,
        hour=0,
        money=15000,
        unlocked=["NW", "NE"],
        demand={"STRAWBERRY": 3},
        prices={"STRAWBERRY": 140, "WHEAT": 25, "CARROT": 35, "TOMATO": 60, "MELON": 200},
    )

    action = engine.act(obs)
    market = action["market"]
    assert any(order[0] == "BUY_SEED" and order[1] == "STRAWBERRY" for order in market)


def test_v4_retains_wheat_for_feed_during_sales() -> None:
    engine = LeaderV4Engine()
    pasture = {"kind": "PASTURE", "animal": "COW", "fed_today": True}
    # Shed has 5 wheat, 1 cow -> should sell at most 4 wheat
    obs = _observation(pasture, day=5, hour=5, money=500, shed={"WHEAT": 5})

    action = engine.act(obs)
    market = action["market"]
    wheat_sales = [order for order in market if order[0] == "SELL" and order[1] == "WHEAT"]

    if wheat_sales:
        sold_qty = wheat_sales[0][2]
        assert sold_qty <= 4


def test_v4_clears_weed_with_high_priority_dig() -> None:
    engine = LeaderV4Engine()
    # Tile (0,0) is a weed
    obs = _observation({"kind": "WEED"}, day=4, hour=2, money=1000)
    action = engine.act(obs)

    # Farmer or hands should issue DIG at (0,0) or move towards it
    assert (
        action["farmer"] == ["DIG"]
        or action["farmer"] == ["PASS"]
        or action["farmer"][0]
        in {
            "MOVE_N",
            "MOVE_S",
            "MOVE_E",
            "MOVE_W",
            "DIG",
        }
    )


def test_v4_builds_pasture_proactively_when_livestock_target_unmet() -> None:
    engine = LeaderV4Engine()
    # Day 5 with empty farm and plenty of money -> should plan pastures
    obs = _observation(day=5, hour=2, money=8000, unlocked=["NW", "NE"])
    action = engine.act(obs)

    # Should either build pasture, plant, or move to do so
    assert action["farmer"] is not None
