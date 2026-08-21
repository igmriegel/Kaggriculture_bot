"""Balanced, deterministic complete-farm policy using verified protocol fields."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from agent.core.contracts import Action
from agent.core.state import NormalizedState


class TaskKind(StrEnum):
    MOVE = "move"
    CLEAR_WEEDS = "clear_weeds"
    HARVEST = "harvest"
    WATER = "water"
    FERTILIZE = "fertilize"
    PLANT = "plant"
    FEED = "feed"
    CARE = "care"
    COLLECT = "collect"
    PICKUP = "pickup"
    DROP = "drop"
    PLACE = "place"
    BUY = "buy"
    SELL = "sell"
    HIRE = "hire"
    BUY_LAND = "buy_land"
    PASS = "pass"


@dataclass(frozen=True)
class Task:
    kind: TaskKind
    target: tuple[int, int] | None = None
    item: str | None = None


@dataclass(frozen=True)
class HeuristicV1Config:
    reserve_cash: int = 10
    closing_turns: int = 24
    seed_name: str = "WHEAT"


class TaskPlanner(Protocol):
    """Derive one eligible task from a normalized state."""

    def plan(self, state: NormalizedState) -> Task: ...


class RoutePlanner(Protocol):
    """Convert a reachable target into one validated movement action."""

    def direction(self, source: tuple[int, int], target: tuple[int, int]) -> str: ...


class MarketPolicy(Protocol):
    """Choose an inventory item to liquidate without exceeding availability."""

    def best_inventory_item(self, state: NormalizedState) -> str | None: ...


class ManhattanRoutePlanner:
    def direction(self, source: tuple[int, int], target: tuple[int, int]) -> str:
        return _direction(source, target)


class PriceMarketPolicy:
    def best_inventory_item(self, state: NormalizedState) -> str | None:
        available = [item for item, amount in state.inventory.items() if amount > 0]
        return max(available, key=lambda item: (state.prices.get(item, 0), item), default=None)


class HeuristicV1:
    """Safety-first V1: protect crops, harvest, sell excess, then grow."""

    def __init__(self, config: HeuristicV1Config | None = None) -> None:
        self.config = config or HeuristicV1Config()
        self.routes: RoutePlanner = ManhattanRoutePlanner()
        self.market: MarketPolicy = PriceMarketPolicy()

    def act(self, observation: dict[str, Any]) -> dict[str, list[Any]]:
        state = NormalizedState.from_observation(observation)
        task = self.plan(state)
        return self.execute(state, task).model_dump()

    def plan(self, state: NormalizedState) -> Task:
        current = state.tile_at_position()
        if current and current.kind == "PLANT" and current.yield_units > 0:
            return Task(TaskKind.HARVEST)
        if current and current.kind == "PLANT" and not current.watered_today:
            return Task(TaskKind.WATER)
        if self._closing(state):
            item = self.market.best_inventory_item(state)
            if item:
                return Task(TaskKind.SELL, item=item)
        if current and current.kind is None and state.seeds.get(self.config.seed_name, 0) > 0:
            return Task(TaskKind.PLANT, item=self.config.seed_name)
        item = self.market.best_inventory_item(state)
        if item and state.inventory[item] > 0:
            return Task(TaskKind.SELL, item=item)
        target = state.nearest_empty()
        if target and (target.x, target.y) != state.position:
            return Task(TaskKind.MOVE, target=(target.x, target.y))
        return Task(TaskKind.PASS)

    def execute(self, state: NormalizedState, task: Task) -> Action:
        if task.kind is TaskKind.HARVEST:
            return Action(farmer=["HARVEST"])
        if task.kind is TaskKind.WATER:
            return Action(farmer=["WATER"])
        if task.kind is TaskKind.FERTILIZE:
            return Action(farmer=["FERTILIZE"])
        if task.kind is TaskKind.PLANT and task.item:
            return Action(farmer=["PLANT", task.item])
        if task.kind is TaskKind.SELL and task.item:
            return Action(farmer=["PASS"], market=[["SELL", task.item, 1]])
        if task.kind is TaskKind.MOVE and task.target:
            return Action(farmer=[self.routes.direction(state.position, task.target)])
        return Action.pass_action()

    def _closing(self, state: NormalizedState) -> bool:
        return (
            state.time_remaining is not None and state.time_remaining <= self.config.closing_turns
        )


def _direction(source: tuple[int, int], target: tuple[int, int]) -> str:
    x, y = source
    target_x, target_y = target
    if target_x > x:
        return "EAST"
    if target_x < x:
        return "WEST"
    if target_y > y:
        return "SOUTH"
    if target_y < y:
        return "NORTH"
    return "PASS"
