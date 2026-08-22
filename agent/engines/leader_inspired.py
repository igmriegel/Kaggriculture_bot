"""State-adaptive policy derived from public evidence in leader replays."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent.core.contracts import Action
from agent.core.state import NormalizedState
from agent.engines.competitive import CompetitiveEngine


@dataclass(frozen=True)
class LeaderInspiredConfig:
    """Conservative bounds around replay-derived animal-first milestones."""

    reserve_cash: int = 150
    opening_animals: int = 4
    target_animals: int = 15
    opening_hires: int = 4
    max_orders: int = 10
    closing_day: int = 28


class LeaderInspiredEngine(CompetitiveEngine):
    """Animal-first, market-aware policy that follows replay phases, not routes."""

    def __init__(self, config: LeaderInspiredConfig | None = None) -> None:
        self.leader_config = config or LeaderInspiredConfig()

    def act(self, observation: dict[str, Any]) -> dict[str, Any]:
        state = NormalizedState.from_observation(observation)
        assigned: set[tuple[int, int]] = set()
        commands = [
            self._leader_command(state, position, index, assigned)
            for index, position in enumerate(state.units())
        ]
        return Action(
            farmer=commands[0], hands=commands[1:], market=self._market_orders(state)
        ).model_dump()

    def _leader_command(
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
        if current and current.animal and not current.fed_today and inventory.get("WHEAT", 0):
            return ["FEED"]
        if current and current.animal and not current.cared_today:
            return ["CARE"]
        if current and current.animal and current.fertilizer_available:
            return ["COLLECT_FERTILIZER"]
        if current and current.kind == "PLANT" and not current.watered_today:
            return ["WATER"]
        if current and current.kind == "WEED":
            return ["DIG"]
        if position in self._shed_tiles(state):
            pickup = self._pickup_item(state, inventory)
            if pickup:
                return ["PICKUP", pickup]
        if current and current.kind is None and self._needs_pasture(state):
            return ["BUILD_PASTURE"]
        if (
            current
            and current.kind == "PASTURE"
            and not current.animal
            and self._carried_animal(inventory)
        ):
            animal = self._carried_animal(inventory)
            return ["PLACE", animal] if animal else ["PASS"]
        if (
            current
            and current.kind is None
            and state.seeds.get(self._crop(state), 0)
            and not self._closing(state)
        ):
            return ["PLANT", self._crop(state)]
        if inventory and position in self._shed_tiles(state):
            return ["DROP"]
        target = self._target(state, position, inventory, assigned)
        if target:
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
        needs_wheat = any(
            tile.animal and not tile.fed_today for tile in state.tiles
        ) and inventory.get("WHEAT", 0)
        if not inventory and self._pickup_item(state, inventory):
            return min(self._shed_tiles(state), key=lambda tile: self._distance(position, tile))
        predicates = (
            lambda tile: self._ripe(tile, state),
            lambda tile: tile.animal and not tile.fed_today and inventory.get("WHEAT", 0),
            lambda tile: tile.animal and not tile.cared_today,
            lambda tile: tile.animal and tile.fertilizer_available,
            lambda tile: tile.kind == "PLANT" and not tile.watered_today,
            lambda tile: tile.kind == "WEED",
            lambda tile: tile.kind == "PASTURE"
            and not tile.animal
            and self._carried_animal(inventory),
            lambda tile: tile.kind is None and self._needs_pasture(state),
            lambda tile: tile.kind is None
            and state.seeds.get(self._crop(state), 0) > 0
            and not self._closing(state),
        )
        for predicate in predicates:
            candidates = [
                tile for tile in state.tiles if predicate(tile) and (tile.x, tile.y) not in assigned
            ]
            if candidates:
                tile = min(
                    candidates,
                    key=lambda item: (self._distance(position, (item.x, item.y)), item.y, item.x),
                )
                return tile.x, tile.y
        if inventory or needs_wheat:
            return min(self._shed_tiles(state), key=lambda tile: self._distance(position, tile))
        return None

    def _market_orders(self, state: NormalizedState) -> list[list[Any]]:
        orders: list[list[Any]] = []
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
        if self._closing(state) or sum(state.shed.values()) >= state.shed_capacity - 6:
            return orders[: self.leader_config.max_orders]
        placed_animals = sum(1 for tile in state.tiles if tile.animal)
        owned_animals = placed_animals + sum(
            state.shed.get(animal, 0) for animal in ("COW", "SHEEP")
        )
        animal_goal = (
            self.leader_config.opening_animals
            if state.day < 4
            else self.leader_config.target_animals
        )
        spending = state.money - self.leader_config.reserve_cash
        if owned_animals < animal_goal and spending >= 400:
            animal = "SHEEP" if owned_animals % 2 == 0 else "COW"
            cost = 500 if animal == "SHEEP" else 400
            if spending >= cost:
                orders.append(["BUY_ANIMAL", animal, 1])
                spending -= cost
        feed_needed = max(0, placed_animals * 2 - state.shed.get("WHEAT", 0))
        if feed_needed and spending >= state.prices.get("WHEAT", 25):
            quantity = min(feed_needed, int(spending // max(1, state.prices.get("WHEAT", 25))))
            if quantity:
                orders.append(["BUY_PRODUCT", "WHEAT", quantity])
        crop = self._crop(state)
        seed_cost = {"WHEAT": 10, "STRAWBERRY": 100, "MELON": 80}[crop]
        seed_needed = max(
            0,
            min(12, len([tile for tile in state.tiles if tile.kind is None]))
            - state.seeds.get(crop, 0),
        )
        if seed_needed and spending >= seed_cost:
            orders.append(["BUY_SEED", crop, min(seed_needed, int(spending // seed_cost))])
        if (
            state.hour < 12
            and state.hires_today < self.leader_config.opening_hires
            and state.money > self.leader_config.reserve_cash + 20
        ):
            orders.append(["HIRE"])
        if (
            state.day >= 6
            and len(state.unlocked_quadrants) < 3
            and state.money > self.leader_config.reserve_cash + 2_000
        ):
            orders.append(["BUY_LAND"])
        return orders[: self.leader_config.max_orders]

    def _crop(self, state: NormalizedState) -> str:
        if state.day >= 14:
            return "WHEAT"
        return "STRAWBERRY" if state.day >= 6 else "WHEAT"

    def _closing(self, state: NormalizedState) -> bool:
        return state.day >= self.leader_config.closing_day

    @staticmethod
    def _carried_animal(inventory: dict[str, int]) -> str | None:
        return next((animal for animal in ("SHEEP", "COW") if inventory.get(animal, 0)), None)

    def _needs_pasture(self, state: NormalizedState) -> bool:
        unplaced = sum(state.shed.get(animal, 0) for animal in ("SHEEP", "COW")) + sum(
            inventory.get(animal, 0)
            for inventory in state.unit_inventories
            for animal in ("SHEEP", "COW")
        )
        pastures = sum(tile.kind == "PASTURE" for tile in state.tiles)
        placed = sum(tile.animal in {"SHEEP", "COW"} for tile in state.tiles)
        return pastures < placed + unplaced

    def _pickup_item(self, state: NormalizedState, inventory: dict[str, int]) -> str | None:
        if inventory:
            return None
        for animal in ("SHEEP", "COW"):
            if state.shed.get(animal, 0):
                return animal
        if state.shed.get("WHEAT", 0) and any(
            tile.animal and not tile.fed_today for tile in state.tiles
        ):
            return "WHEAT"
        return None
