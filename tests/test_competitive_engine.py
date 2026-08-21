from agent.core.validation import validate_action
from agent.engines.competitive import CompetitiveEngine


def _observation(*, tiles, hands=None, private=None, market=None):
    return {
        "player": 0,
        "day": 1,
        "farms": [{"money": 1000, "farmer": [0, 0], "hands": hands or [], "tiles": tiles}],
        "private": private or {"shed": {}, "seeds": {}, "inventories": [{}]},
        "market": market or {"prices": {"WHEAT": 25}},
    }


def test_engine_prioritizes_harvest_and_coordinates_a_hand() -> None:
    obs = _observation(
        tiles=[[{"kind": "PLANT", "yield_units": 2}, {"kind": "PLANT", "watered_today": False}]],
        hands=[[1, 0]],
        private={"shed": {}, "seeds": {}, "inventories": [{}, {}]},
    )
    action = CompetitiveEngine().act(obs)
    assert action["farmer"] == ["HARVEST"]
    assert action["hands"] == [["WATER"]]


def test_engine_liquidates_shed_when_near_capacity() -> None:
    obs = _observation(
        tiles=[[None]],
        private={"shed": {"MILK": 99}, "seeds": {}, "inventories": [{}]},
        market={"prices": {"MILK": 160, "WHEAT": 25}},
    )
    assert CompetitiveEngine().act(obs)["market"] == [["SELL", "MILK", 99]]


def test_validator_rejects_more_hands_than_observed() -> None:
    obs = _observation(tiles=[[None]])
    action, reason = validate_action({"farmer": ["PASS"], "hands": [["PASS"]]}, obs)
    assert action.farmer == ["PASS"]
    assert reason is not None


def test_engine_buys_and_builds_a_goose_project() -> None:
    obs = _observation(tiles=[[None]], private={"shed": {}, "seeds": {}, "inventories": [{}]})
    action = CompetitiveEngine().act(obs)
    assert action["farmer"] == ["BUILD_COOP"]
    assert ["BUY_ANIMAL", "GOOSE", 1] in action["market"]
