from agent.engines.leader_v2 import LeaderV2Engine
from agent.harness.execution import _economic_metrics
from agent.harness.models import TurnRecord


def _observation(*, tiles, private=None, day=0, hour=0, hands=None):
    return {
        "player": 0,
        "day": day,
        "hour": hour,
        "step": day * 24 + hour,
        "farms": [
            {
                "money": 3000,
                "farmer": [4, 4],
                "hands": hands or [],
                "tiles": tiles,
                "unlocked_quadrants": ["NW"],
                "hires_today": 0,
            }
        ],
        "private": private or {"shed": {}, "seeds": {}, "inventories": [{}]},
        "market": {"prices": {"WHEAT": 25}, "inventory": {"WHEAT": 10_000}},
        "town": {"unlocked_shops": []},
    }


def test_leader_v2_uses_bounded_replay_inspired_opening() -> None:
    tiles: list[list[object]] = [
        [None if x < 5 and y < 5 else "LOCKED" for x in range(10)] for y in range(10)
    ]
    action = LeaderV2Engine().act(_observation(tiles=tiles))
    assert ["BUY_ANIMAL", "SHEEP", 2] in action["market"]
    assert ["BUY_ANIMAL", "COW", 2] in action["market"]
    assert action["market"].count(["HIRE"]) == 4


def test_leader_v2_reserves_each_animal_pickup_to_one_unit() -> None:
    tiles: list[list[object]] = [
        [None if x < 5 and y < 5 else "LOCKED" for x in range(10)] for y in range(10)
    ]
    tiles[0][0] = {"kind": "PASTURE"}
    tiles[0][1] = {"kind": "PASTURE"}
    action = LeaderV2Engine().act(
        _observation(
            tiles=tiles,
            day=1,
            private={"shed": {"SHEEP": 1, "COW": 1}, "seeds": {}, "inventories": [{}, {}]},
            hands=[[5, 4]],
        )
    )
    pickups = [
        command for command in [action["farmer"], *action["hands"]] if command[0] == "PICKUP"
    ]
    assert sorted(command[1] for command in pickups) == ["COW", "SHEEP"]


def test_economic_metrics_report_daily_cash_and_logistics() -> None:
    records = [
        TurnRecord(
            turn=0,
            action_sent={
                "farmer": ["PICKUP", "WHEAT"],
                "hands": [],
                "market": [["BUY_PRODUCT", "WHEAT", 2]],
            },
            observation_before={"day": 0, "money": 100},
            observation_after={"day": 0, "money": 50},
        ),
        TurnRecord(
            turn=1,
            action_sent={"farmer": ["HARVEST"], "hands": [], "market": []},
            observation_before={"day": 0, "money": 50},
            observation_after={"day": 0, "money": 75},
        ),
    ]
    metrics = _economic_metrics(records)
    assert metrics["daily"] == [
        {
            "day": 0,
            "money_start": 100,
            "money_end": 75,
            "money_delta": -25,
            "market_orders": {"BUY_PRODUCT": 2},
            "action_counts": {"PICKUP": 1, "HARVEST": 1},
        }
    ]
    assert metrics["shed_operations"] == 1
    assert metrics["harvested_actions"] == 1
