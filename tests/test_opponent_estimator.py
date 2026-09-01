"""Tests for OpponentEstimator."""

from agent.core.state import NormalizedState, Tile
from agent.domain.opponent_estimator import OpponentEstimator


def test_opponent_estimator():
    opp_tile = Tile(x=0, y=0, kind="PLANT", crop="MELON", yield_units=3)
    state = NormalizedState(
        money=1000,
        day=20,
        hour=0,
        step=480,
        position=(0, 0),
        hand_positions=(),
        unlocked_quadrants=(),
        hires_today=0,
        tiles=(),
        seeds={},
        inventory={},
        shed={},
        unit_inventories=(),
        shed_capacity=100,
        board_size=10,
        prices={},
        market_inventory={},
        shops=(),
        demand={},
        time_remaining=None,
        opponent_tiles=(opp_tile,),
        opponent_money=2000,
    )
    estimator = OpponentEstimator()
    est = estimator.estimate(state)

    assert est.estimated_money == 2000
    assert est.estimated_harvest_ready_count == 1
    assert est.crop_counts.get("MELON") == 1
    assert est.threat_level in ("MEDIUM", "HIGH")
