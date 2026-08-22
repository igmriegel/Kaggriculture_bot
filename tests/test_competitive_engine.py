from agent.core.validation import validate_action
from agent.engines.competitive import CompetitiveConfig, CompetitiveEngine
from agent.engines.leader_inspired import LeaderInspiredEngine


def _observation(*, tiles, hands=None, private=None, market=None, day=1):
    return {
        "player": 0,
        "day": day,
        "farms": [{"money": 1000, "farmer": [0, 0], "hands": hands or [], "tiles": tiles}],
        "private": private or {"shed": {}, "seeds": {}, "inventories": [{}]},
        "market": market or {"prices": {"WHEAT": 25}},
    }


def test_engine_prioritizes_harvest_and_coordinates_a_hand() -> None:
    obs = _observation(
        tiles=[
            [
                {"kind": "PLANT", "crop": "CARROT", "planted_day": 0, "yield_units": 2},
                {"kind": "PLANT", "watered_today": False},
            ]
        ],
        hands=[[1, 0]],
        private={"shed": {}, "seeds": {}, "inventories": [{}, {}]},
        day=2,
    )
    action = CompetitiveEngine(CompetitiveConfig(enable_hands=True)).act(obs)
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


def test_engine_starts_with_bounded_carrot_seeds() -> None:
    obs = _observation(tiles=[[None]], private={"shed": {}, "seeds": {}, "inventories": [{}]})
    action = CompetitiveEngine().act(obs)
    assert action["farmer"] == ["PASS"]
    assert action["market"] == [["BUY_SEED", "CARROT", 4]]


def test_engine_never_harvests_immature_crop() -> None:
    obs = _observation(
        tiles=[[{"kind": "PLANT", "crop": "CARROT", "planted_day": 1, "yield_units": 1}]],
        day=1,
    )
    assert CompetitiveEngine().act(obs)["farmer"] == ["WATER"]


def test_engine_hires_one_hand_for_a_busy_day() -> None:
    obs = _observation(
        tiles=[[None, None], [None, None]],
        private={"shed": {}, "seeds": {"CARROT": 4}, "inventories": [{}]},
    )
    action = CompetitiveEngine(CompetitiveConfig(enable_hands=True)).act(obs)
    assert ["HIRE"] in action["market"]


def test_leader_inspired_engine_invests_in_animal_opening() -> None:
    obs = _observation(tiles=[[None]], private={"shed": {}, "seeds": {}, "inventories": [{}]})
    action = LeaderInspiredEngine().act(obs)
    assert ["BUY_ANIMAL", "SHEEP", 1] in action["market"]
    assert ["BUY_SEED", "WHEAT", 1] in action["market"]
    assert ["HIRE"] in action["market"]


def test_leader_inspired_engine_prioritizes_animal_care() -> None:
    obs = _observation(
        tiles=[[{"kind": "PASTURE", "animal": "COW", "fed_today": True, "cared_today": False}]],
        private={"shed": {}, "seeds": {}, "inventories": [{}]},
    )
    assert LeaderInspiredEngine().act(obs)["farmer"] == ["CARE"]


def test_leader_inspired_engine_picks_up_bought_animals_before_planting() -> None:
    tiles: list[list[object]] = [["LOCKED"] * 10 for _ in range(10)]
    tiles[4][4] = None
    obs = _observation(
        tiles=tiles,
        private={"shed": {"SHEEP": 1}, "seeds": {"WHEAT": 1}, "inventories": [{}]},
    )
    obs["farms"][0]["farmer"] = [4, 4]
    assert LeaderInspiredEngine().act(obs)["farmer"] == ["PICKUP", "SHEEP"]
