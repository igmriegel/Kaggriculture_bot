"""Spatial planning: concentric Manhattan zoning, route chaining, and bipartite task assignment."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from agent.core.state import NormalizedState, Tile


@dataclass(frozen=True)
class Task:
    target: tuple[int, int]
    action_type: str
    priority: int  # lower is higher priority


def manhattan_distance(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def direction_towards(source: tuple[int, int], target: tuple[int, int]) -> str:
    x, y = source
    tx, ty = target
    if tx > x:
        return "EAST"
    if tx < x:
        return "WEST"
    if ty > y:
        return "SOUTH"
    if ty < y:
        return "NORTH"
    return "PASS"


def prioritize_unlocked_tiles_by_shed_proximity(
    tiles: Sequence[Tile],
    shed_tiles: Sequence[tuple[int, int]],
    predicate: Callable[[Tile], bool] | None = None,
) -> list[Tile]:
    """Sort tiles by minimum Manhattan distance to central shed tiles."""
    candidates = [t for t in tiles if predicate is None or predicate(t)]

    def min_dist_to_shed(tile: Tile) -> tuple[int, int, int]:
        dist = min(manhattan_distance((tile.x, tile.y), s) for s in shed_tiles)
        return (dist, tile.y, tile.x)

    return sorted(candidates, key=min_dist_to_shed)


def solve_linear_assignment(cost_matrix: list[list[int]]) -> list[int]:
    """Simple exact matching for small worker counts (N <= 4)."""
    n_workers = len(cost_matrix)
    if n_workers == 0:
        return []
    n_tasks = len(cost_matrix[0]) if n_workers > 0 else 0
    if n_tasks == 0:
        return [-1] * n_workers

    import itertools

    if n_tasks >= n_workers:
        best_cost = float("inf")
        best_perm: tuple[int, ...] = tuple(range(n_workers))
        for perm in itertools.permutations(range(n_tasks), n_workers):
            cost = sum(cost_matrix[w][perm[w]] for w in range(n_workers))
            if cost < best_cost:
                best_cost = cost
                best_perm = perm
        return list(best_perm)
    else:
        # Fewer tasks than workers: some workers get -1
        best_cost = float("inf")
        best_assignment = [-1] * n_workers
        for worker_subset in itertools.combinations(range(n_workers), n_tasks):
            for task_perm in itertools.permutations(range(n_tasks)):
                cost = sum(
                    cost_matrix[w][t] for w, t in zip(worker_subset, task_perm, strict=False)
                )
                if cost < best_cost:
                    best_cost = cost
                    curr = [-1] * n_workers
                    for w, t in zip(worker_subset, task_perm, strict=False):
                        curr[w] = t
                    best_assignment = curr
        return best_assignment


class SpatialPlanner:
    """Coordinates movement and task allocation for the farmer and hired hands."""

    def __init__(self, state: NormalizedState) -> None:
        self.state = state
        self.shed_tiles = state.shed_tiles()

    def find_best_planting_tile(self) -> Tile | None:
        """Pick empty unlocked tile closest to the shed."""
        sorted_empty = prioritize_unlocked_tiles_by_shed_proximity(
            self.state.tiles,
            self.shed_tiles,
            predicate=lambda t: t.kind is None,
        )
        return sorted_empty[0] if sorted_empty else None

    def assign_tasks(
        self,
        worker_positions: Sequence[tuple[int, int]],
        tasks: Sequence[Task],
    ) -> list[Task | None]:
        """Assign tasks to workers globally minimizing total worker-to-task travel distance."""
        if not tasks:
            return [None] * len(worker_positions)

        # Sort tasks by priority first
        sorted_tasks = sorted(tasks, key=lambda t: t.priority)

        cost_matrix: list[list[int]] = []
        for w_pos in worker_positions:
            row: list[int] = []
            for task in sorted_tasks:
                dist = manhattan_distance(w_pos, task.target)
                # Weighted by priority
                cost = dist + (task.priority * 50)
                row.append(cost)
            cost_matrix.append(row)

        assignment = solve_linear_assignment(cost_matrix)
        result: list[Task | None] = []
        for idx in assignment:
            result.append(sorted_tasks[idx] if idx >= 0 and idx < len(sorted_tasks) else None)
        return result
