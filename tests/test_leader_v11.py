"""Unit tests for Leader V11 Hybrid Engine."""

from agent.core.state import NormalizedState
from agent.engines.leader_v11 import LeaderV11Engine


def _observation(day: int = 1, hour: int = 1, money: int = 3000) -> dict:
    tiles = []
    for y in range(10):
        row = []
        for x in range(10):
            row.append(
                {
                    "x": x,
                    "y": y,
                    "kind": None,
                    "crop": None,
                    "animal": None,
                    "watered_today": False,
                    "yield_units": 0,
                }
            )
        tiles.append(row)

    return {
        "player": 0,
        "day": day,
        "hour": hour,
        "step": day * 24 + hour,
        "farms": [
            {
                "money": money,
                "farmer": [4, 4],
                "hands": [],
                "unlocked_quadrants": ["NW"],
                "hires_today": 0,
                "tiles": tiles,
            },
            {
                "money": money,
                "farmer": [4, 4],
                "hands": [],
                "unlocked_quadrants": ["NW"],
                "hires_today": 0,
                "tiles": tiles,
            },
        ],
        "market": {
            "inventory": {
                "WHEAT": 10000,
                "CARROT": 10000,
                "TOMATO": 10000,
                "STRAWBERRY": 10000,
                "MELON": 10000,
            },
            "prices": {
                "WHEAT": 25,
                "CARROT": 35,
                "TOMATO": 60,
                "STRAWBERRY": 120,
                "MELON": 250,
            },
        },
        "town": {"unlocked_shops": ["BAKERY"]},
        "private": {
            "shed": {"WHEAT": 0, "STRAWBERRY": 0},
            "seeds": {"WHEAT": 0, "STRAWBERRY": 0},
            "inventories": [{}],
        },
    }


def test_leader_v11_act_returns_valid_dict() -> None:
    engine = LeaderV11Engine()
    obs = _observation(day=5, hour=1, money=4000)
    action = engine.act(obs)
    assert isinstance(action, dict)
    assert "farmer" in action
    assert "hands" in action
    assert "market" in action


def test_leader_v11_mc_roi_adjustment() -> None:
    engine = LeaderV11Engine()
    obs = _observation(day=5, hour=1, money=4000)
    state = NormalizedState.from_observation(obs)
    roi = engine._calculate_marginal_tile_roi(
        "STRAWBERRY", state, horizon=25, current_planned_tiles=0
    )
    assert roi >= 0.0
