from agent.core.state import NormalizedState
from agent.engines.heuristic_v1 import HeuristicV1, TaskKind


def observation(tile, *, seeds=None, inventory=None, market=None, remaining=None):
    result = {
        "player": 0,
        "private": {"seeds": seeds or {}, "inventory": inventory or {}},
        "market": market or {},
        "farms": [{"money": 100, "farmer": [0, 0], "tiles": [[tile]]}],
    }
    if remaining is not None:
        result["time_remaining"] = remaining
    return result


def test_v1_harvests_before_watering_or_growth() -> None:
    engine = HeuristicV1()
    action = engine.act(observation({"kind": "PLANT", "watered_today": False, "yield_units": 1}))
    assert action["farmer"] == ["HARVEST"]


def test_v1_plants_only_available_seed_at_current_empty_tile() -> None:
    assert HeuristicV1().act(observation(None, seeds={"WHEAT": 1}))["farmer"] == ["PLANT", "WHEAT"]


def test_v1_uses_market_price_for_liquidation() -> None:
    action = HeuristicV1().act(
        observation(
            None,
            inventory={"APPLE": 1, "MILK": 1},
            market={"prices": {"APPLE": 2, "MILK": 5}},
        )
    )
    assert action["market"] == [["SELL", "MILK", 1]]


def test_v1_closing_season_prioritizes_sale() -> None:
    engine = HeuristicV1()
    state = engine.plan(
        NormalizedState.from_observation(observation(None, inventory={"APPLE": 1}, remaining=1))
    )
    assert state.kind is TaskKind.SELL
