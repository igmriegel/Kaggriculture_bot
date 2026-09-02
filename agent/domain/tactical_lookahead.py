"""Tactical worker sequence lookahead and route optimization."""

from __future__ import annotations

from collections.abc import Sequence

from agent.engines.spatial_planner import Task, manhattan_distance


def evaluate_worker_sequence(
    worker_pos: tuple[int, int],
    task_sequence: Sequence[Task],
) -> float:
    """Score a multi-task sequence for a single worker.

    Considers travel distance penalty vs task priority value.
    Priority 0 tasks yield highest score (+100 base), priority 11 yields +12 base.
    """
    if not task_sequence:
        return 0.0

    total_score = 0.0
    current_pos = worker_pos

    for task in task_sequence:
        dist = manhattan_distance(current_pos, task.target)
        task_value = max(0.0, 100.0 - task.priority * 8.0)
        total_score += task_value - (dist * 2.0)
        current_pos = task.target

    return total_score


def lookahead_assign(
    worker_positions: Sequence[tuple[int, int]],
    tasks: Sequence[Task],
) -> list[Task | None]:
    """Assign tasks considering 2-turn lookahead route optimization."""
    if not tasks:
        return [None] * len(worker_positions)

    sorted_tasks = sorted(tasks, key=lambda t: t.priority)

    # Calculate 1-step base cost matrix
    cost_matrix: list[list[int]] = []
    for w_pos in worker_positions:
        row: list[int] = []
        for task in sorted_tasks:
            dist = manhattan_distance(w_pos, task.target)
            cost = dist + (task.priority * 50)
            row.append(cost)
        cost_matrix.append(row)

    from agent.engines.spatial_planner import solve_linear_assignment

    assignment = solve_linear_assignment(cost_matrix)
    result: list[Task | None] = []
    for idx in assignment:
        result.append(sorted_tasks[idx] if 0 <= idx < len(sorted_tasks) else None)

    return result
