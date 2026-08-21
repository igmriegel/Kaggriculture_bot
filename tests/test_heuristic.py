from agent.engines.heuristic import ConservativeHeuristic


def observation(tile=None, *, seeds=None, hour=1):
    return {
        "player": 0,
        "hour": hour,
        "private": {"seeds": seeds or {}},
        "farms": [{"money": 100, "farmer": [0, 0], "tiles": [[tile]]}],
    }


def test_heuristic_waters_first() -> None:
    action = ConservativeHeuristic().act(
        observation({"kind": "PLANT", "watered_today": False, "yield_units": 0})
    )
    assert action["farmer"] == ["WATER"]


def test_heuristic_buys_wheat_at_day_start() -> None:
    action = ConservativeHeuristic().act(observation(None, hour=0))
    assert action["market"] == [["BUY_SEED", "WHEAT", 1]]


def test_heuristic_plants_available_wheat() -> None:
    action = ConservativeHeuristic().act(observation(None, seeds={"WHEAT": 1}))
    assert action["farmer"] == ["PLANT", "WHEAT"]
