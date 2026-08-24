from agent.core.validation import validate_action


def test_valid_action_survives_validation() -> None:
    action, reason = validate_action({"farmer": ["PLANT", "WHEAT"], "market": []})
    assert reason is None
    assert action.farmer == ["PLANT", "WHEAT"]


def test_malformed_action_falls_back_to_pass() -> None:
    action, reason = validate_action({"farmer": ["NOT_AN_ACTION"]})
    assert action.farmer == ["PASS"]
    assert reason is not None


def test_observation_validation_rejects_out_of_bounds_move() -> None:
    observation = {
        "player": 0,
        "farms": [{"farmer": [0, 0], "hands": [], "tiles": [[None]]}],
        "private": {"shed": {}, "seeds": {}, "inventories": [{}]},
    }
    action, reason = validate_action({"farmer": ["NORTH"]}, observation)
    assert action.farmer == ["PASS"]
    assert reason is not None


def test_observation_validation_accepts_seeded_plant() -> None:
    observation = {
        "player": 0,
        "farms": [{"farmer": [0, 0], "hands": [], "tiles": [[None]]}],
        "private": {"shed": {}, "seeds": {"WHEAT": 1}, "inventories": [{}]},
    }
    action, reason = validate_action({"farmer": ["PLANT", "WHEAT"]}, observation)
    assert reason is None
    assert action.farmer == ["PLANT", "WHEAT"]


def test_invalid_unit_command_does_not_discard_valid_market_order() -> None:
    observation = {
        "player": 0,
        "farms": [
            {
                "farmer": [4, 4],
                "hands": [],
                "tiles": [
                    [None if x < 5 and y < 5 else "LOCKED" for x in range(10)] for y in range(10)
                ],
            }
        ],
        "private": {"shed": {"WHEAT": 1}, "seeds": {}, "inventories": [{}]},
    }

    action, reason = validate_action(
        {"farmer": ["PICKUP", "WHEAT", 2], "market": [["HIRE"]]}, observation
    )

    assert action.farmer == ["PASS"]
    assert action.market == [["HIRE"]]
    assert reason == "ValueError: pickup exceeds shed inventory"
