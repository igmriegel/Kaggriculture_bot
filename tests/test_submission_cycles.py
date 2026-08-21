from main import agent


def _observation(tile, *, inventory=None, shed=None, seeds=None):
    return {
        "player": 0,
        "day": 5,
        "hour": 1,
        "step": 121,
        "farms": [{"money": 3000, "farmer": [0, 0], "hands": [], "tiles": [[tile]]}],
        "private": {
            "shed": shed or {},
            "seeds": seeds or {},
            "inventories": [inventory or {}],
        },
        "market": {"inventory": {"WHEAT": 10000}, "prices": {"WHEAT": 25}},
        "town": {"unlocked_shops": []},
    }


def test_submission_harvest_cycle_is_not_downgraded() -> None:
    action = agent(
        _observation(
            {
                "kind": "PLANT",
                "crop": "CARROT",
                "planted_day": 0,
                "yield_units": 2,
                "watered_today": False,
            }
        )
    )
    assert action["farmer"] == ["HARVEST"]


def test_submission_feeds_animal_from_unit_inventory() -> None:
    action = agent(
        _observation(
            {"kind": "COOP", "animal": "GOOSE", "fed_today": False}, inventory={"WHEAT": 1}
        )
    )
    assert action["farmer"] == ["FEED"]


def test_submission_collects_animal_fertilizer() -> None:
    action = agent(_observation({"kind": "COOP", "animal": "GOOSE", "fertilizer_available": True}))
    assert action["farmer"] == ["COLLECT_FERTILIZER"]
