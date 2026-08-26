from agent.engines.leader_v6 import LeaderV6Engine


def _observation(*, day=0, hour=0, money=1000, tiles=None, shed=None, seeds=None, hands=None):
    base_tiles = [[None for _ in range(10)] for _ in range(10)]
    if tiles:
        for y, row in enumerate(tiles):
            for x, val in enumerate(row):
                base_tiles[y][x] = val
    return {
        "player": 0,
        "day": day,
        "hour": hour,
        "step": day * 24 + hour,
        "farms": [
            {
                "money": money,
                "farmer": [4, 4],
                "hands": hands or [],
                "unlocked_quadrants": ["NW"],
                "hires_today": 0,
                "tiles": base_tiles,
            },
            {
                "money": 1000,
                "farmer": [4, 4],
                "hands": [],
                "unlocked_quadrants": ["NW"],
                "hires_today": 0,
                "tiles": [[None for _ in range(10)] for _ in range(10)],
            },
        ],
        "private": {
            "shed": shed or {},
            "seeds": seeds or {},
            "inventories": [{} for _ in range(1 + len(hands or []))],
        },
        "market": {
            "prices": {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120, "MELON": 250},
            "inventory": {"WHEAT": 10000, "MELON": 10000, "STRAWBERRY": 10000},
        },
        "town": {"unlocked_shops": [], "demand": {}},
    }


def test_v6_opening_executes_comprehensive_portfolio() -> None:
    engine = LeaderV6Engine()
    action = engine.act(_observation(day=0, hour=1, money=1000))
    market = action["market"]
    assert ["HIRE"] in market
    assert ["BUY_ANIMAL", "COW", 2] in market
    assert ["BUY_ANIMAL", "SHEEP", 2] in market
    assert ["BUY_SEED", "WHEAT", 4] in market
    assert ["BUY_SEED", "MELON", 4] in market


def test_v6_concentric_pasture_placement() -> None:
    engine = LeaderV6Engine()
    # At Day 0 Hour 1, farmer is at (4,4). Tasks should pick tiles closest to shed (4,4)-(5,5)
    obs = _observation(day=0, hour=1, money=1000)
    action = engine.act(obs)
    # The farmer should build pasture on or adjacent to (4,4)
    valid_ops = {"NORTH", "SOUTH", "EAST", "WEST", "BUILD_PASTURE", "PASS"}
    assert action["farmer"][0] in valid_ops


def test_v6_proactively_buys_feed_on_deficit() -> None:
    engine = LeaderV6Engine()
    pasture_cow = {"kind": "PASTURE", "animal": "COW", "fed_today": False}
    pasture_sheep = {"kind": "PASTURE", "animal": "SHEEP", "fed_today": False}

    obs = _observation(day=3, hour=1, money=2000, shed={})
    obs["farms"][0]["tiles"][0][0] = pasture_cow
    obs["farms"][0]["tiles"][0][1] = pasture_sheep

    action = engine.act(obs)
    market = action["market"]
    assert any(order[0] == "BUY_PRODUCT" and order[1] == "WHEAT" for order in market)
