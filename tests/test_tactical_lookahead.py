"""Unit tests for Tactical Worker Lookahead."""

from agent.domain.tactical_lookahead import evaluate_worker_sequence, lookahead_assign
from agent.engines.spatial_planner import Task


def test_evaluate_worker_sequence() -> None:
    worker_pos = (4, 4)
    tasks = [
        Task(target=(4, 5), action_type="HARVEST", priority=1),
        Task(target=(4, 6), action_type="WATER", priority=4),
    ]
    score = evaluate_worker_sequence(worker_pos, tasks)
    assert score > 0.0


def test_lookahead_assign_matches_workers() -> None:
    worker_positions = [(4, 4), (5, 5)]
    tasks = [
        Task(target=(4, 5), action_type="HARVEST", priority=1),
        Task(target=(5, 6), action_type="WATER", priority=4),
    ]
    assigned = lookahead_assign(worker_positions, tasks)
    assert len(assigned) == 2
    assert assigned[0] is not None
    assert assigned[1] is not None
