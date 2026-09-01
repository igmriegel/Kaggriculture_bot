"""Tests for StateEncoder feature extraction."""

from agent.core.encoder import StateEncoder
from agent.core.state import NormalizedState, Tile


def test_state_encoder():
    tile = Tile(x=0, y=0, kind="PLANT", crop="WHEAT", yield_units=2)
    state = NormalizedState(
        money=500,
        day=15,
        hour=12,
        step=372,
        position=(2, 2),
        hand_positions=(),
        unlocked_quadrants=(),
        hires_today=0,
        tiles=(tile,),
        seeds={"WHEAT": 5},
        inventory={"WHEAT": 20},
        shed={"WHEAT": 20},
        unit_inventories=(),
        shed_capacity=100,
        board_size=10,
        prices={"WHEAT": 12.0},
        market_inventory={},
        shops=(),
        demand={},
        time_remaining=None,
    )
    encoder = StateEncoder()
    encoded = encoder.encode(state)

    assert len(encoded.vector) == len(encoded.feature_names)
    feat_dict = encoded.to_dict()
    assert "day_norm" in feat_dict
    assert feat_dict["day_norm"] == 15 / 30.0
    assert feat_dict["plant_ratio"] == 1.0
