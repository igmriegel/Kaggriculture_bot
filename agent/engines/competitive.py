"""Deterministic, legality-first full-farm policy for the official rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent.core.contracts import Action
from agent.core.state import NormalizedState

_CROP_COST = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}
_YIELD_VALUE = {"WHEAT": 150, "CARROT": 140, "TOMATO": 240, "STRAWBERRY": 480, "MELON": 1500}


@dataclass(frozen=True)
class CompetitiveConfig:
    reserve_cash: int = 100
    closing_turns: int = 48
    max_orders: int = 10


class CompetitiveEngine:
    """Coordinates farmer and hands: protect assets, route work, then invest."""

    def __init__(self, config: CompetitiveConfig | None = None) -> None:
        self.config = config or CompetitiveConfig()

    def act(self, observation: dict[str, Any]) -> dict[str, Any]:
        state = NormalizedState.from_observation(observation)
        assigned: set[tuple[int, int]] = set()
        commands = [
            self._unit_command(state, pos, i, assigned) for i, pos in enumerate(state.units())
        ]
        return Action(
            farmer=commands[0], hands=commands[1:], market=self._market_orders(state)
        ).model_dump()

    def _unit_command(
        self,
        state: NormalizedState,
        pos: tuple[int, int],
        index: int,
        assigned: set[tuple[int, int]],
    ) -> list[Any]:
        tile = state.tile_at(pos)
        inv = state.unit_inventories[index] if index < len(state.unit_inventories) else {}
        if tile and tile.kind == "PLANT" and tile.yield_units > 0:
            return ["HARVEST"]
        if tile and tile.animal and tile.yield_units > 0:
            return ["HARVEST"]
        if tile and tile.kind == "PLANT" and not tile.watered_today:
            return ["WATER"]
        if tile and tile.animal and not tile.fed_today and inv.get("WHEAT", 0):
            return ["FEED"]
        if tile and tile.kind == "WEED":
            return ["DIG"]
        if tile and tile.animal and tile.fertilizer_available:
            return ["COLLECT_FERTILIZER"]
        if tile and tile.animal and not tile.cared_today:
            return ["CARE"]
        if inv and pos in self._shed_tiles(state):
            return ["DROP"]
        target = self._target(state, pos, inv, assigned)
        if target:
            assigned.add(target)
            return [self._direction(pos, target)]
        if tile and tile.kind is None and state.seeds.get(self._best_crop(state), 0):
            return ["PLANT", self._best_crop(state)]
        return ["PASS"]

    def _target(
        self,
        state: NormalizedState,
        pos: tuple[int, int],
        inv: dict[str, int],
        assigned: set[tuple[int, int]],
    ) -> tuple[int, int] | None:
        predicates = (
            lambda t: t.kind == "PLANT" and t.yield_units > 0,
            lambda t: bool(t.animal and t.yield_units > 0),
            lambda t: t.kind == "PLANT" and not t.watered_today,
            lambda t: bool(t.animal and not t.fed_today and inv.get("WHEAT", 0)),
            lambda t: t.kind == "WEED",
            lambda t: bool(t.animal and t.fertilizer_available),
            lambda t: bool(t.animal and not t.cared_today),
            lambda t: t.kind is None and state.seeds.get(self._best_crop(state), 0) > 0,
        )
        for predicate in predicates:
            choices = [t for t in state.tiles if predicate(t) and (t.x, t.y) not in assigned]
            if choices:
                chosen = min(choices, key=lambda t: (self._distance(pos, (t.x, t.y)), t.y, t.x))
                return chosen.x, chosen.y
        if inv:
            return min(self._shed_tiles(state), key=lambda p: self._distance(pos, p))
        return None

    def _market_orders(self, state: NormalizedState) -> list[list[Any]]:
        orders: list[list[Any]] = []
        full = sum(state.shed.values()) >= state.shed_capacity - 4
        for item, amount in sorted(
            state.shed.items(), key=lambda pair: (-state.prices.get(pair[0], 0), pair[0])
        ):
            if amount > 0 and (full or self._closing(state)):
                orders.append(["SELL", item, amount])
        if self._closing(state) or full:
            return orders[: self.config.max_orders]
        crop = self._best_crop(state)
        empty = sum(tile.kind is None for tile in state.tiles)
        wanted = max(0, min(empty, 8) - state.seeds.get(crop, 0))
        affordable = max(0, int((state.money - self.config.reserve_cash) // _CROP_COST[crop]))
        if wanted and affordable:
            orders.append(["BUY_SEED", crop, min(wanted, affordable)])
        urgent = sum(
            t.kind == "PLANT" and not t.watered_today or t.kind == "WEED" or bool(t.animal)
            for t in state.tiles
        )
        if urgent > len(state.units()) * 2 and state.money > self.config.reserve_cash + 1:
            orders.append(["HIRE"])
        return orders[: self.config.max_orders]

    def _best_crop(self, state: NormalizedState) -> str:
        candidates = [
            crop
            for crop in _CROP_COST
            if 30 - state.day >= (2 if crop in {"WHEAT", "CARROT"} else 8)
        ]
        return max(
            candidates or ["WHEAT"],
            key=lambda c: (
                state.prices.get(c, _YIELD_VALUE[c] / 6) * _YIELD_VALUE[c] / _CROP_COST[c],
                c,
            ),
        )

    def _closing(self, state: NormalizedState) -> bool:
        return (
            state.time_remaining is not None and state.time_remaining <= self.config.closing_turns
        )

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
    def _distance(a: tuple[int, int], b: tuple[int, int]) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    @staticmethod
    def _shed_tiles(state: NormalizedState) -> tuple[tuple[int, int], ...]:
        size = max((max(t.x, t.y) for t in state.tiles), default=9) + 1
        half = size // 2
        return ((half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half))
