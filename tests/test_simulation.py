"""Tests for forward simulation and state evaluation."""

from agent.core.simulation import ForwardSimulator, evaluate_state_value
from agent.core.state import NormalizedState, Tile


def test_forward_simulator_movement():
    state = NormalizedState(
        money=100,
        day=5,
        hour=10,
        step=130,
        position=(5, 5),
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
    )
    sim = ForwardSimulator()
    next_state = sim.step_action(state, ("NORTH",))
    assert next_state.position == (5, 4)

    next_state2 = sim.step_action(state, ("EAST",))
    assert next_state2.position == (6, 5)


def test_evaluate_state_value():
    tile = Tile(x=0, y=0, kind="PLANT", crop="WHEAT", yield_units=5)
    state = NormalizedState(
        money=200,
        day=10,
        hour=0,
        step=240,
        position=(0, 0),
        hand_positions=(),
        unlocked_quadrants=(),
        hires_today=0,
        tiles=(tile,),
        seeds={"WHEAT": 2},
        inventory={"WHEAT": 10},
        shed={"WHEAT": 10},
        unit_inventories=(),
        shed_capacity=100,
        board_size=10,
        prices={},
        market_inventory={},
        shops=(),
        demand={},
        time_remaining=None,
    )
    score = evaluate_state_value(state)
    assert score > 200.0
