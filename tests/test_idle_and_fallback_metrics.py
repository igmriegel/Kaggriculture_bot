from agent.analysis.action_metrics import classify_action, summarize_turns
from agent.core.validation import validate_action
from agent.engines.leader_v2 import LeaderV2Engine
from agent.engines.leader_v3 import LeaderV3Engine


def _observation(*, tile, farmer=(1, 1), hands=None, shed=None, money=3000, day=1, hour=0):
    board = [[None for _ in range(5)] for _ in range(5)]
    board[0][0] = tile
    return {
        "player": 0,
        "day": day,
        "hour": hour,
        "step": day * 24 + hour,
        "farms": [
            {
                "money": money,
                "farmer": list(farmer),
                "hands": hands or [],
                "hires_today": 0,
                "tiles": board,
                "unlocked_quadrants": ["NW"],
            }
        ],
        "private": {
            "shed": shed or {},
            "seeds": {},
            "inventories": [{} for _ in range(1 + len(hands or []))],
        },
        "market": {"prices": {"WHEAT": 25}, "inventory": {"WHEAT": 1}},
    }


def test_one_unit_feed_pickup_is_not_converted_to_pass() -> None:
    observation = _observation(
        tile={"kind": "PASTURE", "animal": "COW", "fed_today": False},
        shed={"WHEAT": 1},
    )
    action = LeaderV2Engine().act(observation)

    assert action["farmer"] == ["PICKUP", "WHEAT", 1]
    validated, reason = validate_action(action, observation)
    assert reason is None
    assert validated.model_dump() == action


def test_turn_metrics_distinguish_legitimate_wait_idle_and_fallback() -> None:
    records = [
        {"action_sent": {"farmer": ["PASS"], "hands": [], "market": []}, "observation_before": {}},
        {
            "action_sent": {"farmer": ["PASS"], "hands": [], "market": []},
            "observation_before": {"hungry_animals": 1},
        },
        {
            "action_sent": {"farmer": ["PASS"], "hands": [], "market": []},
            "action_raw": {"farmer": ["BROKEN"]},
            "fallback_reason": "invalid command",
            "observation_before": {},
        },
        {"action_sent": {"farmer": ["EAST"], "hands": [], "market": []}, "observation_before": {}},
    ]

    metrics = summarize_turns(records)

    assert metrics["turn_classes"] == {
        "idle_pass": 1,
        "legitimate_wait": 1,
        "fallback_pass": 1,
        "movement": 1,
    }
    assert metrics["idle_turn_percentage"] == 25.0
    assert metrics["longest_pass_streak"] == 3
    assert metrics["fallbacks_inferred"] == 1
    assert metrics["lost_actions"] == 1
    assert metrics["heatmap"]["0:0"]["idle_pass"] == 1


def test_v3_rehires_only_for_productive_work_after_daily_reset() -> None:
    board = [[{"kind": "PLANT", "watered_today": False} for _ in range(4)]]
    observation = _observation(tile=None, farmer=(0, 0), day=2, hour=0, money=1000)
    observation["farms"][0]["tiles"] = board
    observation["private"]["inventories"] = [{}]

    action = LeaderV3Engine().act(observation)

    assert action["farmer"] == ["WATER"]
    assert action["market"].count(["HIRE"]) >= 1
    assert classify_action(action, {}) == "productive"
