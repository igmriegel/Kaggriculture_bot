"""Cycle-complete, state-adaptive Kaggriculture policy."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from agent.core.contracts import Action
from agent.core.state import NormalizedState, Tile
from agent.domain.economics import projected_prices
from agent.engines.competitive import CompetitiveEngine

_PRODUCTS = {
    "WHEAT",
    "CARROT",
    "TOMATO",
    "STRAWBERRY",
    "MELON",
    "EGG",
    "MILK",
    "WOOL",
    "FERTILIZER",
}
_ANIMAL_COST = {"COW": 400, "SHEEP": 500}
_SEED_COST = {"WHEAT": 10, "STRAWBERRY": 100, "MELON": 80}


@dataclass(frozen=True)
class DailyBudget:
    reserve: int
    feed: int
    investment: int
    labor: int


@dataclass(frozen=True)
class ProductionGoal:
    name: str
    quantity: int
    deadline_day: int


@dataclass(frozen=True)
class Task:
    priority: int
    target: tuple[int, int]
    command: list[Any]
    eligible: Callable[[dict[str, int]], bool] = lambda inventory: not inventory
    reservation: tuple[str, object] | None = None


@dataclass(frozen=True)
class LeaderV2Config:
    reserve_cash: int = 0
    operating_cash_floor: int = 150
    opening_animals: int = 4
    max_animals: int = 22
    max_hands: int = 12
    max_orders: int = 10
    closing_day: int = 28


class LeaderV2Engine(CompetitiveEngine):
    """Plans profitable production cycles before assigning individual actions."""

    def __init__(self, config: LeaderV2Config | None = None) -> None:
        self.v2_config = config or LeaderV2Config()

    def act(self, observation: dict[str, Any]) -> dict[str, Any]:
        state = NormalizedState.from_observation(observation)
        goals = self._goals(state)
        tasks = self._tasks(state, goals)
        commands = self._allocate(state, tasks)
        return Action(
            farmer=commands[0],
            hands=commands[1:],
            market=self._build_market_orders(state, goals, tasks),
        ).model_dump()

    def _goals(self, state: NormalizedState) -> tuple[ProductionGoal, ...]:
        target_animals = self.v2_config.opening_animals if state.day < 5 else 8
        if 10 <= state.day < 20:
            target_animals = self.v2_config.max_animals
        if state.day >= 20:
            target_animals = self._animal_count(state)
        crop = "STRAWBERRY" if 6 <= state.day < 17 else "WHEAT"
        crop_slots = 0 if self._pending_animals(state) else min(12, self._empty_tiles(state))
        return (
            ProductionGoal("operational_animals", target_animals, min(18, state.day + 4)),
            ProductionGoal(f"plant_{crop.lower()}", crop_slots, state.day + 1),
        )

    def _tasks(self, state: NormalizedState, goals: tuple[ProductionGoal, ...]) -> list[Task]:
        del goals
        tasks: list[Task] = []
        opening = state.day == 0
        for tile in state.tiles:
            point = (tile.x, tile.y)
            if self._ripe(tile, state):
                tasks.append(Task(1, point, ["HARVEST"], reservation=("tile", point)))
                continue
            if tile.animal:
                if not tile.fed_today:
                    tasks.append(Task(2, point, ["FEED"], _has_wheat, ("tile", point)))
                if tile.fertilizer_available:
                    # Feed and care are production obligations. Fertilizer is
                    # collected afterwards because it remains available until
                    # a worker reaches the tile.
                    tasks.append(
                        Task(
                            4,
                            point,
                            ["COLLECT_FERTILIZER"],
                            _empty_inventory,
                            ("tile", point),
                        )
                    )
                elif not tile.cared_today:
                    tasks.append(Task(3, point, ["CARE"], _empty_inventory, ("tile", point)))
                continue
            if tile.kind == "PLANT" and not tile.watered_today:
                tasks.append(
                    Task(4 if opening else 5, point, ["WATER"], _empty_inventory, ("tile", point))
                )

        pending = self._pending_animals(state)
        open_pastures = [tile for tile in state.tiles if tile.kind == "PASTURE" and not tile.animal]
        planned_animals = (
            self.v2_config.opening_animals
            if state.day == 0 and state.hour == 1 and not any(state.shed.values())
            else pending
        )
        build_count = max(0, planned_animals - len(open_pastures))
        for tile in sorted(
            (tile for tile in state.tiles if tile.kind is None),
            key=lambda tile: (self._distance(state.position, (tile.x, tile.y)), tile.y, tile.x),
        )[:build_count]:
            point = (tile.x, tile.y)
            tasks.append(
                Task(
                    1 if opening else 5, point, ["BUILD_PASTURE"], _empty_inventory, ("tile", point)
                )
            )
        for tile in open_pastures:
            point = (tile.x, tile.y)
            tasks.append(Task(2 if opening else 6, point, ["PLACE"], _has_animal, ("tile", point)))
        for index, animal in enumerate(self._shed_animals(state)):
            point = self._shed_tiles(state)[index % len(self._shed_tiles(state))]
            tasks.append(
                Task(
                    0 if opening else 7,
                    point,
                    ["PICKUP", animal],
                    _empty_inventory,
                    ("pickup", index),
                )
            )
        hungry_animals = sum(1 for tile in state.tiles if tile.animal and not tile.fed_today)
        feed_pickups = min(len(self._shed_tiles(state)), (hungry_animals + 1) // 2)
        available_wheat = state.shed.get("WHEAT", 0)
        if available_wheat > 0 and feed_pickups:
            # A pickup is validated against the stock currently in the shed.
            # Requesting two units with a one-unit reserve previously invalidated
            # the whole turn, including otherwise legal market orders.
            feed_quantity = min(2, available_wheat)
            for index, point in enumerate(self._shed_tiles(state)[:feed_pickups]):
                tasks.append(
                    Task(
                        0,
                        point,
                        ["PICKUP", "WHEAT", feed_quantity],
                        _empty_inventory,
                        ("wheat", index),
                    )
                )

        if not pending or state.day == 0:
            crops = ("WHEAT", "MELON") if state.day == 0 else (self._crop(state),)
            empty_tiles = [tile for tile in state.tiles if tile.kind is None]
            for crop in crops:
                for tile in empty_tiles[: state.seeds.get(crop, 0)]:
                    point = (tile.x, tile.y)
                    tasks.append(
                        Task(
                            3 if opening else 9,
                            point,
                            ["PLANT", crop],
                            _empty_inventory,
                            ("tile", point),
                        )
                    )
                empty_tiles = empty_tiles[state.seeds.get(crop, 0) :]
        for tile in state.tiles:
            if tile.kind == "WEED":
                point = (tile.x, tile.y)
                tasks.append(Task(10, point, ["DIG"], _empty_inventory, ("tile", point)))
        for index, inventory in enumerate(state.unit_inventories):
            if inventory and any(item in _PRODUCTS for item in inventory):
                point = state.units()[index]
                if point in self._shed_tiles(state):
                    tasks.append(Task(11, point, ["DROP"], reservation=("unit", index)))
        return tasks

    def _allocate(self, state: NormalizedState, tasks: list[Task]) -> list[list[Any]]:
        positions = state.units()
        inventories = [
            state.unit_inventories[index] if index < len(state.unit_inventories) else {}
            for index in range(len(positions))
        ]
        commands: list[list[Any]] = [["PASS"] for _ in positions]
        free = set(range(len(positions)))
        reserved: set[tuple[str, object]] = set()
        for task in sorted(tasks, key=lambda item: item.priority):
            if task.reservation and task.reservation in reserved:
                continue
            candidates = [index for index in free if task.eligible(inventories[index])]
            if not candidates:
                continue
            unit = min(
                candidates, key=lambda index: (self._distance(positions[index], task.target), index)
            )
            if positions[unit] == task.target:
                commands[unit] = self._command_for(task, inventories[unit])
            else:
                commands[unit] = [self._direction(positions[unit], task.target)]
            free.remove(unit)
            if task.reservation:
                reserved.add(task.reservation)
        return commands

    @staticmethod
    def _command_for(task: Task, inventory: dict[str, int]) -> list[Any]:
        if task.command == ["PLACE"]:
            animal = next(animal for animal in ("SHEEP", "COW") if inventory.get(animal, 0))
            return ["PLACE", animal]
        return task.command

    def _build_market_orders(
        self, state: NormalizedState, goals: tuple[ProductionGoal, ...], tasks: list[Task]
    ) -> list[list[Any]]:
        if state.day == 0 and not any(state.shed.values()) and not self._animal_count(state):
            if state.hour == 0:
                return []
            if state.hour == 1:
                return [
                    ["HIRE"],
                    ["HIRE"],
                    ["HIRE"],
                    ["HIRE"],
                    ["HIRE"],
                    ["BUY_ANIMAL", "SHEEP", 2],
                    ["BUY_ANIMAL", "COW", 2],
                    ["BUY_SEED", "MELON", 11],
                    ["BUY_SEED", "WHEAT", 6],
                    ["BUY_PRODUCT", "WHEAT", 4],
                ]
        budget = self._budget(state, tasks)
        projected = projected_prices(
            state.market_inventory, state.shops, state.step, max(0, 720 - state.step)
        )
        orders = self._sales(state, projected)
        spending = max(0, state.money - budget.reserve)
        if self._closing(state):
            return orders[: self.v2_config.max_orders]
        animal_goal = next(goal.quantity for goal in goals if goal.name == "operational_animals")
        if self._pending_animals(state) == 0 and self._animal_count(state) < animal_goal:
            animal = "SHEEP" if self._animal_count(state) % 2 == 0 else "COW"
            if (
                state.money
                >= _ANIMAL_COST[animal] + budget.feed + self.v2_config.operating_cash_floor
            ):
                orders.append(["BUY_ANIMAL", animal, 1])
                spending -= _ANIMAL_COST[animal]
        shortfall = self._wheat_shortfall(state)
        if shortfall and spending >= budget.feed:
            quantity = min(shortfall, int(spending // max(1, state.prices.get("WHEAT", 25))))
            if quantity:
                orders.append(["BUY_PRODUCT", "WHEAT", quantity])
                spending -= quantity * int(state.prices.get("WHEAT", 25))
        crop = self._crop(state)
        seed_goal = next(goal.quantity for goal in goals if goal.name == f"plant_{crop.lower()}")
        seed_needed = max(0, seed_goal - state.seeds.get(crop, 0))
        seed_spending = max(0, spending - self.v2_config.operating_cash_floor)
        if seed_needed and seed_spending >= _SEED_COST[crop]:
            quantity = min(seed_needed, int(seed_spending // _SEED_COST[crop]))
            orders.append(["BUY_SEED", crop, quantity])
            spending -= quantity * _SEED_COST[crop]
        productive = sum(task.priority < 10 for task in tasks)
        target_hands = self._hand_target(state)
        prospective_hires = state.hires_today
        while (
            state.hour == 1
            and len(state.hand_positions) + prospective_hires - state.hires_today < target_hands
            and productive > len(state.units()) + 2
            and len(orders) < self.v2_config.max_orders
        ):
            hire_cost = self._hire_cost(prospective_hires)
            if spending < hire_cost:
                break
            orders.append(["HIRE"])
            spending -= hire_cost
            prospective_hires += 1
        land_cost = (
            (1000, 2000, 4000)[max(0, len(state.unlocked_quadrants) - 1)]
            if len(state.unlocked_quadrants) < 4
            else 0
        )
        if (
            state.day >= 6
            and len(state.unlocked_quadrants) < 3
            and spending >= land_cost + budget.feed
        ):
            orders.append(["BUY_LAND"])
        return orders[: self.v2_config.max_orders]

    def _budget(self, state: NormalizedState, tasks: list[Task]) -> DailyBudget:
        wheat_price = int(state.prices.get("WHEAT", 25))
        feed = self._wheat_shortfall(state) * wheat_price
        labor = self._hire_cost(state.hires_today) if len(tasks) > len(state.units()) else 0
        return DailyBudget(self.v2_config.reserve_cash, feed, max(0, state.money - feed), labor)

    def _sales(self, state: NormalizedState, projected: dict[str, int]) -> list[list[Any]]:
        orders: list[list[Any]] = []
        pressure = sum(state.shed.values()) >= state.shed_capacity - 8
        for item, amount in sorted(state.shed.items()):
            if item not in _PRODUCTS or amount <= 0:
                continue
            retain = (
                # Food is an operational reserve, not surplus. Retaining one
                # full feeding cycle gives the allocator time to collect it
                # from the shed before the following daily refresh.
                self._animal_count(state) if item == "WHEAT" else 0
            )
            recurring_cashflow = item == "FERTILIZER" or (
                item in {"EGG", "MILK", "WOOL"} and amount >= 4
            )
            if (
                pressure
                or self._closing(state)
                or state.money < self.v2_config.operating_cash_floor
                or recurring_cashflow
                or projected.get(item, 0) <= state.prices.get(item, 0)
            ):
                quantity = max(0, amount - retain)
                if quantity:
                    orders.append(["SELL", item, quantity])
        return orders

    def _crop(self, state: NormalizedState) -> str:
        return "STRAWBERRY" if 6 <= state.day < 17 else "WHEAT"

    def _closing(self, state: NormalizedState) -> bool:
        return state.day >= self.v2_config.closing_day

    def _hand_target(self, state: NormalizedState) -> int:
        if state.day <= 1:
            return 1
        if state.day == 2:
            return 3
        if state.day <= 5:
            return 4
        if state.day <= 9:
            return 7
        if self._closing(state):
            return min(8, self.v2_config.max_hands)
        return self.v2_config.max_hands

    @staticmethod
    def _ripe(tile: Tile, state: NormalizedState) -> bool:
        first_yield = {"WHEAT": 2, "CARROT": 2, "TOMATO": 8, "STRAWBERRY": 10, "MELON": 10}
        return bool(
            tile.animal
            and tile.yield_units > 0
            or (
                tile.kind == "PLANT"
                and tile.yield_units > 0
                and tile.crop in first_yield
                and tile.planted_day is not None
                and state.day - tile.planted_day >= first_yield[tile.crop]
            )
        )

    @staticmethod
    def _hire_cost(hired: int) -> int:
        first, second = 1, 1
        for _ in range(hired):
            first, second = second, first + second
        return first

    @staticmethod
    def _empty_tiles(state: NormalizedState) -> int:
        return sum(tile.kind is None for tile in state.tiles)

    @staticmethod
    def _animal_count(state: NormalizedState) -> int:
        return sum(tile.animal in _ANIMAL_COST for tile in state.tiles)

    def _pending_animals(self, state: NormalizedState) -> int:
        return len(self._shed_animals(state)) + sum(
            inventory.get(animal, 0)
            for inventory in state.unit_inventories
            for animal in _ANIMAL_COST
        )

    @staticmethod
    def _shed_animals(state: NormalizedState) -> list[str]:
        return [animal for animal in ("SHEEP", "COW") for _ in range(state.shed.get(animal, 0))]

    def _wheat_shortfall(self, state: NormalizedState) -> int:
        owned = state.shed.get("WHEAT", 0) + sum(
            inventory.get("WHEAT", 0) for inventory in state.unit_inventories
        )
        return max(0, self._animal_count(state) - owned)


def _empty_inventory(inventory: dict[str, int]) -> bool:
    return not inventory


def _has_wheat(inventory: dict[str, int]) -> bool:
    return inventory.get("WHEAT", 0) > 0


def _has_animal(inventory: dict[str, int]) -> bool:
    return any(inventory.get(animal, 0) for animal in _ANIMAL_COST)
