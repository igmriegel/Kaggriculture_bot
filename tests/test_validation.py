from agent.core.validation import validate_action


def test_valid_action_survives_validation() -> None:
    action, reason = validate_action({"farmer": ["PLANT", "WHEAT"], "market": []})
    assert reason is None
    assert action.farmer == ["PLANT", "WHEAT"]


def test_malformed_action_falls_back_to_pass() -> None:
    action, reason = validate_action({"farmer": ["NOT_AN_ACTION"]})
    assert action.farmer == ["PASS"]
    assert reason is not None
