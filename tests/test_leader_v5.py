from agent.engines.leader_v5 import LeaderV5Engine


def _observation(
    tile: dict | None = None,
    *,
    day: int = 0,
    hour: int = 0,
    step: int = 0,
    money: int = 3000,
    shed: dict | None = None,
    unlocked: list[str] | None = None,
) -> dict:
    tiles = [[None for _ in range(10)] for _ in range(10)]
    if tile is not None:
        tiles[4][4] = tile
    return {
        "player": 0,
        "step": step,
        "day": day,
        "hour": hour,
        "farms": [
            {
                "money": money,
                "farmer": [4, 4],
                "hands": [],
                "unlocked_quadrants": unlocked or ["NW"],
                "hires_today": 0,
                "tiles": tiles,
            },
            {
                "money": 1000,
                "farmer": [0, 0],
                "hands": [],
                "unlocked_quadrants": ["NW"],
                "hires_today": 0,
                "tiles": [[None for _ in range(10)] for _ in range(10)],
            },
        ],
        "market": {
            "inventory": {"WHEAT": 10, "CARROT": 10, "MELON": 10, "COW": 2, "SHEEP": 2},
            "prices": {"WHEAT": 25.0, "CARROT": 35.0, "MELON": 250.0},
        },
        "town": {
            "demand": {"MELON": 10, "MILK": 10, "WOOL": 10},
            "unlocked_shops": ["DAIRY", "SPINNING"],
        },
        "private": {
            "seeds": {},
            "shed": shed or {},
            "inventories": [{}],
        },
    }


def test_v5_opening_executes_comprehensive_portfolio() -> None:
    engine = LeaderV5Engine()
    obs = _observation(day=0, hour=1, money=3000)
    action = engine.act(obs)

    market = action["market"]
    assert ["HIRE"] in market
    assert ["BUY_ANIMAL", "COW", 2] in market
    assert ["BUY_ANIMAL", "SHEEP", 2] in market
    assert ["BUY_PRODUCT", "WHEAT", 4] in market


def test_v5_proactively_buys_feed_on_deficit() -> None:
    engine = LeaderV5Engine()
    pasture = {"kind": "PASTURE", "animal": "COW", "fed_today": False}
    # Out of wheat in shed -> should order wheat feed
    obs = _observation(pasture, day=2, hour=1, money=1000, shed={"WHEAT": 0})
    action = engine.act(obs)

    market = action["market"]
    assert any(order[0] == "BUY_PRODUCT" and order[1] == "WHEAT" for order in market)


def test_v5_retains_animal_feed_in_sales() -> None:
    engine = LeaderV5Engine()
    pasture = {"kind": "PASTURE", "animal": "COW", "fed_today": True}
    # Shed has 5 wheat, 1 cow -> should sell at most 3 wheat (retaining at least 2)
    obs = _observation(pasture, day=5, hour=5, money=500, shed={"WHEAT": 5})

    action = engine.act(obs)
    market = action["market"]
    wheat_sales = [order for order in market if order[0] == "SELL" and order[1] == "WHEAT"]

    if wheat_sales:
        sold_qty = wheat_sales[0][2]
        assert sold_qty <= 3


def test_v5_clears_weed_with_high_priority_dig() -> None:
    engine = LeaderV5Engine()
    obs = _observation({"kind": "WEED"}, day=4, hour=2, money=1000)
    action = engine.act(obs)
    assert action["farmer"] == ["DIG"]


def test_v5_escalates_water_priority_on_drought_risk() -> None:
    engine = LeaderV5Engine()
    plant_tile = {
        "kind": "PLANT",
        "crop": "WHEAT",
        "watered_today": False,
        "consecutive_unwatered": 1,
        "planted_day": 2,
    }
    obs = _observation(plant_tile, day=3, hour=10, money=1000)
    action = engine.act(obs)
    assert action["farmer"] == ["WATER"]


def test_v5_escalates_harvest_priority_on_decay_risk() -> None:
    engine = LeaderV5Engine()
    plant_tile = {
        "kind": "PLANT",
        "crop": "STRAWBERRY",
        "yield_units": 2,
        "watered_today": True,
        "max_lifespan_step": 300,
        "planted_day": 1,
    }
    obs = _observation(plant_tile, day=12, hour=10, step=290, money=1000)
    action = engine.act(obs)
    assert action["farmer"] == ["HARVEST"]
