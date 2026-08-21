"""Deterministic crop-first policy built directly from Kaggriculture rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent.core.contracts import Action
from agent.core.state import NormalizedState, Tile

_CROP = "CARROT"
_SEED_COST = 20
_FIRST_YIELD_DAY = 2
_CLOSING_DAY = 28


@dataclass(frozen=True)
class CompetitiveConfig:
    """Conservative limits for the reproducible crop-first opening."""

    reserve_cash: int = 200
    seed_batch: int = 4
    closing_day: int = _CLOSING_DAY
    max_orders: int = 10
    enable_hands: bool = False


class CompetitiveEngine:
    """Protect production first, then turn every harvested item into money.

    Carrots are deliberately selected for the opening because their two-day
    maturity gives one worker a short, verifiable production loop. Expansion is
    deferred until the harness demonstrates reliable positive cashflow.
    """

    def __init__(self, config: CompetitiveConfig | None = None) -> None:
        self.config = config or CompetitiveConfig()

    def act(self, observation: dict[str, Any]) -> dict[str, Any]:
        state = NormalizedState.from_observation(observation)
        assigned: set[tuple[int, int]] = set()
        commands = [
            self._unit_command(state, position, index, assigned)
            for index, position in enumerate(state.units())
        ]
        return Action(
            farmer=commands[0], hands=commands[1:], market=self._market_orders(state)
        ).model_dump()

    def _unit_command(
        self,
        state: NormalizedState,
        position: tuple[int, int],
        index: int,
        assigned: set[tuple[int, int]],
    ) -> list[Any]:
        current = state.tile_at(position)
        inventory = state.unit_inventories[index] if index < len(state.unit_inventories) else {}

        if current and self._ripe(current, state):
            return ["HARVEST"]
        if current and current.kind == "PLANT" and not current.watered_today:
            return ["WATER"]
        if current and current.animal and not current.fed_today and inventory.get("WHEAT", 0):
            return ["FEED"]
        if current and current.animal and current.fertilizer_available:
            return ["COLLECT_FERTILIZER"]
        if current and current.animal and not current.cared_today:
            return ["CARE"]
        if current and current.kind == "WEED":
            return ["DIG"]
        if inventory and position in self._shed_tiles(state):
            return ["DROP"]
        if (
            current
            and current.kind is None
            and state.seeds.get(_CROP, 0)
            and not self._closing(state)
        ):
            return ["PLANT", _CROP]

        target = self._target(state, position, inventory, assigned)
        if target is not None:
            assigned.add(target)
            return [self._direction(position, target)]
        return ["PASS"]

    def _target(
        self,
        state: NormalizedState,
        position: tuple[int, int],
        inventory: dict[str, int],
        assigned: set[tuple[int, int]],
    ) -> tuple[int, int] | None:
        predicates = (
            lambda tile: self._ripe(tile, state),
            lambda tile: tile.kind == "PLANT" and not tile.watered_today,
            lambda tile: tile.kind == "WEED",
            lambda tile: tile.kind is None
            and state.seeds.get(_CROP, 0) > 0
            and not self._closing(state),
        )
        for predicate in predicates:
            candidates = [
                tile for tile in state.tiles if predicate(tile) and (tile.x, tile.y) not in assigned
            ]
            if candidates:
                target = min(
                    candidates,
                    key=lambda tile: (self._distance(position, (tile.x, tile.y)), tile.y, tile.x),
                )
                return target.x, target.y
        if inventory:
            return min(self._shed_tiles(state), key=lambda tile: self._distance(position, tile))
        return None

    def _market_orders(self, state: NormalizedState) -> list[list[Any]]:
        orders: list[list[Any]] = []
        # Products only: animals are assets that must be placed, never sold.
        for item, amount in sorted(state.shed.items()):
            if amount > 0 and item in {
                "WHEAT",
                "CARROT",
                "TOMATO",
                "STRAWBERRY",
                "MELON",
                "EGG",
                "MILK",
                "WOOL",
                "FERTILIZER",
            }:
                orders.append(["SELL", item, amount])
        if self._closing(state) or sum(state.shed.values()) >= state.shed_capacity - 4:
            return orders[: self.config.max_orders]
        needed = max(0, self.config.seed_batch - state.seeds.get(_CROP, 0))
        affordable = max(0, int((state.money - self.config.reserve_cash) // _SEED_COST))
        if needed and affordable:
            orders.append(["BUY_SEED", _CROP, min(needed, affordable)])
        # A hand lasts only until day-end. Hire exactly one at the opening of a
        # busy day: its Fibonacci first cost is $1, while it can plant/water
        # several carrots before the daily refresh.
        pending = sum(
            tile.kind == "WEED"
            or (tile.kind == "PLANT" and not tile.watered_today)
            or (tile.kind is None and state.seeds.get(_CROP, 0) > 0)
            for tile in state.tiles
        )
        if (
            self.config.enable_hands
            and state.hour == 0
            and state.hires_today == 0
            and pending >= 4
            and state.money > self.config.reserve_cash + 1
        ):
            orders.append(["HIRE"])
        return orders[: self.config.max_orders]

    def _closing(self, state: NormalizedState) -> bool:
        return state.day >= self.config.closing_day

    @staticmethod
    def _ripe(tile: Tile, state: NormalizedState) -> bool:
        return (
            tile.kind == "PLANT"
            and tile.yield_units > 0
            and tile.crop == _CROP
            and tile.planted_day is not None
            and state.day - tile.planted_day >= _FIRST_YIELD_DAY
        ) or (tile.animal is not None and tile.yield_units > 0)

    @staticmethod
    def _direction(source: tuple[int, int], target: tuple[int, int]) -> str:
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

    @staticmethod
    def _distance(first: tuple[int, int], second: tuple[int, int]) -> int:
        return abs(first[0] - second[0]) + abs(first[1] - second[1])

    @staticmethod
    def _shed_tiles(state: NormalizedState) -> tuple[tuple[int, int], ...]:
        size = max((max(tile.x, tile.y) for tile in state.tiles), default=9) + 1
        half = size // 2
        return ((half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half))
