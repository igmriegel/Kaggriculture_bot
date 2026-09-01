"""Unit tests for Opponent Tracker."""

from agent.core.state import NormalizedState
from agent.domain.opponent_model import OpponentTracker


def _fake_observation(
    day: int = 1,
    step: int = 24,
    opp_money: int = 3000,
    opp_crops: list[str] | None = None,
) -> dict:
    grid = []
    crop_idx = 0
    for y in range(10):
        row = []
        for x in range(10):
            tile_dict = {
                "x": x,
                "y": y,
                "kind": None,
                "crop": None,
                "animal": None,
                "watered_today": False,
                "yield_units": 0,
            }
            if opp_crops and crop_idx < len(opp_crops) and y == 0 and x < len(opp_crops):
                tile_dict["kind"] = "PLANT"
                tile_dict["crop"] = opp_crops[crop_idx]
                tile_dict["yield_units"] = 4
                crop_idx += 1
            row.append(tile_dict)
        grid.append(row)

    return {
        "player": 0,
        "day": day,
        "hour": 0,
        "step": step,
        "farms": [
            {
                "money": 3000,
                "farmer": [4, 4],
                "hands": [],
                "unlocked_quadrants": ["NW"],
                "hires_today": 0,
                "tiles": grid,
            },
            {
                "money": opp_money,
                "farmer": [4, 4],
                "hands": [],
                "unlocked_quadrants": ["NW"],
                "hires_today": 0,
                "tiles": grid,
            },
        ],
        "market": {"inventory": {}, "prices": {}},
        "town": {"unlocked_shops": []},
        "private": {"shed": {}, "seeds": {}, "inventories": [{}]},
    }


def test_opponent_tracker_accumulates_crop_counts() -> None:
    tracker = OpponentTracker()
    obs1 = _fake_observation(day=1, step=24, opp_money=3000, opp_crops=["STRAWBERRY", "MELON"])
    state1 = NormalizedState.from_observation(obs1)
    prof1 = tracker.update(state1)
    assert prof1.crop_counts.get("STRAWBERRY", 0) == 1
    assert prof1.crop_counts.get("MELON", 0) == 1
    assert prof1.aggression_score >= 0.0


def test_opponent_tracker_detects_sell_bulk() -> None:
    tracker = OpponentTracker()
    obs1 = _fake_observation(day=1, step=24, opp_money=3000)
    tracker.update(NormalizedState.from_observation(obs1))

    obs2 = _fake_observation(day=1, step=25, opp_money=4200)
    prof2 = tracker.update(NormalizedState.from_observation(obs2))
    assert prof2.estimated_sell_timing == "bulk"
