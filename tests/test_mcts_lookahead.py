"""Tests for MCTSLookaheadEngine."""

from agent.engines.mcts_lookahead import MCTSLookaheadEngine


def test_mcts_lookahead_engine_act():
    engine = MCTSLookaheadEngine()
    obs = {
        "player": 0,
        "day": 1,
        "hour": 0,
        "step": 0,
        "farms": [
            {
                "money": 500,
                "farmer": [0, 0],
                "tiles": [[{"kind": "PLANT", "watered_today": False, "yield_units": 0}]],
            },
            {"money": 500, "farmer": [0, 0], "tiles": [[]]},
        ],
        "private": {"seeds": {"WHEAT": 5}, "shed": {}},
        "market": {"prices": {"WHEAT": 10.0}},
        "town": {},
    }
    action = engine.act(obs)
    assert isinstance(action, dict)
    assert "farmer" in action
    assert isinstance(action["farmer"], list)
