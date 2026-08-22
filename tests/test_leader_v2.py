from agent.core.state import NormalizedState
from agent.engines.leader_v2 import LeaderV2Engine
from agent.harness.execution import _economic_metrics
from agent.harness.models import TurnRecord


def _observation(*, tiles, private=None, day=0, hour=0, hands=None, money=3000):
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
    action = LeaderV2Engine().act(_observation(tiles=tiles, hour=1))

    assert action["farmer"] == ["BUILD_PASTURE"]
    assert ["BUY_ANIMAL", "SHEEP", 2] in action["market"]
    assert ["BUY_ANIMAL", "COW", 2] in action["market"]
    assert ["BUY_SEED", "MELON", 11] in action["market"]
    assert ["BUY_SEED", "WHEAT", 6] in action["market"]
    assert ["BUY_PRODUCT", "WHEAT", 4] in action["market"]
    assert action["market"].count(["HIRE"]) == 5


def test_leader_v2_waits_for_the_replay_inspired_opening_turn() -> None:
    tiles: list[list[object]] = [
        [None if x < 5 and y < 5 else "LOCKED" for x in range(10)] for y in range(10)
    ]

    assert LeaderV2Engine().act(_observation(tiles=tiles))["market"] == []


def test_leader_v2_hires_the_replay_phase_target_for_a_busy_day() -> None:
    tiles: list[list[object]] = [
        [
            {"kind": "PLANT", "crop": "WHEAT", "watered_today": False}
            if x < 5 and y < 5
            else "LOCKED"
            for x in range(10)
        ]
        for y in range(10)
    ]
    action = LeaderV2Engine().act(_observation(tiles=tiles, day=2, hour=1))

    assert action["market"].count(["HIRE"]) == 3


def test_leader_v2_collects_feed_before_other_animal_work() -> None:
    tiles: list[list[object]] = [
        [
            {"kind": "PASTURE", "animal": "COW"}
            if y == 0 and x < 4
            else None
            if x < 5 and y < 5
            else "LOCKED"
            for x in range(10)
        ]
        for y in range(10)
    ]
    action = LeaderV2Engine().act(
        _observation(
            tiles=tiles,
            day=1,
            private={"shed": {"WHEAT": 8}, "seeds": {}, "inventories": [{}]},
        )
    )

    assert action["farmer"] == ["PICKUP", "WHEAT", 2]


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


def test_leader_v2_retains_one_daily_wheat_ration_before_selling() -> None:
    tiles: list[list[object]] = [
        [
            {"kind": "PASTURE", "animal": "COW"}
            if x < 4 and y == 0
            else None
            if x < 5 and y < 5
            else "LOCKED"
            for x in range(10)
        ]
        for y in range(10)
    ]
    engine = LeaderV2Engine()
    observation = _observation(
        tiles=tiles,
        day=2,
        private={"shed": {"WHEAT": 8}, "seeds": {}, "inventories": [{}]},
    )
    normalized = NormalizedState.from_observation(observation)

    assert engine._sales(normalized, {"WHEAT": 25}) == [["SELL", "WHEAT", 4]]


def test_leader_v2_liquidates_products_for_emergency_operating_cash() -> None:
    tiles: list[list[object]] = [
        [None if x < 5 and y < 5 else "LOCKED" for x in range(10)] for y in range(10)
    ]
    state = NormalizedState.from_observation(
        _observation(
            tiles=tiles,
            money=10,
            private={"shed": {"WOOL": 2}, "seeds": {}, "inventories": [{}]},
        )
    )

    assert LeaderV2Engine()._sales(state, {"WOOL": 300}) == [["SELL", "WOOL", 2]]


def test_leader_v2_sells_fertilizer_as_recurring_cashflow() -> None:
    tiles: list[list[object]] = [
        [None if x < 5 and y < 5 else "LOCKED" for x in range(10)] for y in range(10)
    ]
    state = NormalizedState.from_observation(
        _observation(
            tiles=tiles,
            private={"shed": {"FERTILIZER": 2}, "seeds": {}, "inventories": [{}]},
        )
    )

    assert LeaderV2Engine()._sales(state, {"FERTILIZER": 500}) == [["SELL", "FERTILIZER", 2]]


def test_leader_v2_does_not_divert_carried_feed_to_fertilizer_collection() -> None:
    tiles: list[list[object]] = [
        [
            {
                "kind": "PASTURE",
                "animal": "COW",
                "fed_today": True,
                "fertilizer_available": True,
            }
            if x == 4 and y == 4
            else None
            if x < 5 and y < 5
            else "LOCKED"
            for x in range(10)
        ]
        for y in range(10)
    ]
    action = LeaderV2Engine().act(
        _observation(
            tiles=tiles,
            day=2,
            private={"shed": {}, "seeds": {}, "inventories": [{"WHEAT": 1}]},
        )
    )

    assert action["farmer"] == ["PASS"]


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
