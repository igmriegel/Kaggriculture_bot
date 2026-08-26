from agent.core.state import Tile
from agent.domain.roi import (
    calculate_closing_day,
    estimate_opponent_expected_harvests,
)
from agent.engines.spatial_planner import (
    prioritize_unlocked_tiles_by_shed_proximity,
    solve_linear_assignment,
)


def test_calculate_closing_day():
    assert calculate_closing_day("WHEAT", 30) == 28
    assert calculate_closing_day("CARROT", 30) == 28
    assert calculate_closing_day("TOMATO", 30) == 22
    assert calculate_closing_day("STRAWBERRY", 30) == 20
    assert calculate_closing_day("MELON", 30) == 20


def test_estimate_opponent_harvests():
    opp_tiles = (
        Tile(0, 0, "PLANT", crop="CARROT"),
        Tile(0, 1, "PLANT", crop="CARROT"),
        Tile(1, 0, "PLANT", crop="MELON"),
        Tile(1, 1, "COOP", animal="GOOSE"),
    )
    harvests = estimate_opponent_expected_harvests(opp_tiles)
    assert harvests["CARROT"] == 8
    assert harvests["MELON"] == 6
    assert harvests["EGG"] == 10


def test_solve_linear_assignment():
    # 2 workers, 2 tasks
    # Worker 0 close to task 0 (dist 1) vs task 1 (dist 10)
    # Worker 1 close to task 1 (dist 2) vs task 0 (dist 8)
    cost_matrix = [
        [1, 10],
        [8, 2],
    ]
    assignment = solve_linear_assignment(cost_matrix)
    assert assignment == [0, 1]


def test_prioritize_tiles_concentric():
    tiles = [
        Tile(0, 0, None),  # far from shed
        Tile(3, 4, None),  # adjacent to shed (4,4)
        Tile(1, 1, None),
    ]
    shed_tiles = ((4, 4), (5, 4), (4, 5), (5, 5))
    sorted_tiles = prioritize_unlocked_tiles_by_shed_proximity(tiles, shed_tiles)
    assert (sorted_tiles[0].x, sorted_tiles[0].y) == (3, 4)
