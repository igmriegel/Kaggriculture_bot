"""Deterministic crop and livestock policy with dynamic ROI and spatial optimization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent.core.contracts import Action
from agent.core.state import NormalizedState, Tile
from agent.domain.roi import CROPS_SPEC, best_crop_to_plant, calculate_closing_day
from agent.engines.spatial_planner import (
    SpatialPlanner,
    Task,
    direction_towards,
    manhattan_distance,
    prioritize_unlocked_tiles_by_shed_proximity,
)


@dataclass(frozen=True)
class CompetitiveConfig:
    """Limits and parameters for competitive execution."""

    reserve_cash: int = 150
    seed_batch: int = 4
    max_orders: int = 10
    enable_hands: bool = True
    enable_coop: bool = True
    crop: str | None = "CARROT"


class CompetitiveEngine:
    """Optimized engine combining ROI crop selection and spatial clustering."""

    def __init__(self, config: CompetitiveConfig | None = None) -> None:
        self.config = config or CompetitiveConfig()

    def act(self, observation: dict[str, Any]) -> dict[str, Any]:
        state = NormalizedState.from_observation(observation)
        planner = SpatialPlanner(state)

        # 1. Collect all potential tasks across the farm
        tasks = self._gather_tasks(state)

        # 2. Assign tasks to units using optimal assignment
        units = state.units()
        assigned_tasks = planner.assign_tasks(units, tasks)

        # 3. Generate unit commands
        commands = [
            self._unit_step(state, pos, idx, assigned_tasks[idx]) for idx, pos in enumerate(units)
        ]

        return Action(
            farmer=commands[0],
            hands=commands[1:],
            market=self._market_orders(state),
        ).model_dump()

    def _gather_tasks(self, state: NormalizedState) -> list[Task]:
        tasks: list[Task] = []

        for tile in state.tiles:
            pos = (tile.x, tile.y)
            # Priority 0: Harvest ripe crops or animals
            if self._ripe(tile, state):
                tasks.append(Task(pos, "HARVEST", priority=0))
            # Priority 1: Water unwatered plants
            elif tile.kind == "PLANT" and not tile.watered_today:
                tasks.append(Task(pos, "WATER", priority=1))
            # Priority 2: Animal care (feed, care, collect fertilizer)
            elif tile.animal:
                if not tile.fed_today or not tile.cared_today or tile.fertilizer_available:
                    tasks.append(Task(pos, "ANIMAL_CARE", priority=2))
            # Priority 3: Clear weeds
            elif tile.kind == "WEED":
                tasks.append(Task(pos, "DIG", priority=3))
            # Priority 4: Plant in empty tiles closest to shed
            elif tile.kind is None and self._has_viable_seeds(state):
                tasks.append(Task(pos, "PLANT", priority=4))

        return tasks

    def _unit_step(
        self,
        state: NormalizedState,
        position: tuple[int, int],
        index: int,
        task: Task | None,
    ) -> list[Any]:
        current = state.tile_at(position)
        inventory = state.unit_inventories[index] if index < len(state.unit_inventories) else {}
        shed_tiles = state.shed_tiles()

        # Immediate on-tile executions take precedence
        if current and self._ripe(current, state):
            return ["HARVEST"]
        if current and current.kind == "PLANT" and not current.watered_today:
            return ["WATER"]
        if current and current.animal:
            if not current.fed_today and inventory.get("WHEAT", 0):
                return ["FEED"]
            if current.fertilizer_available:
                return ["COLLECT_FERTILIZER"]
            if not current.cared_today:
                return ["CARE"]
        if current and current.kind == "WEED":
            return ["DIG"]

        # Drop inventory when at the shed
        if inventory and position in shed_tiles:
            return ["DROP"]

        # Plant on empty tile if holding seed
        if current and current.kind is None:
            chosen_crop = self._select_seed_to_plant(state)
            if chosen_crop and state.seeds.get(chosen_crop, 0) > 0:
                return ["PLANT", chosen_crop]

        # If holding items and shed is needed, route to shed
        if sum(inventory.values()) >= 2:
            nearest_shed = min(shed_tiles, key=lambda s: manhattan_distance(position, s))
            if position != nearest_shed:
                return [direction_towards(position, nearest_shed)]

        # Move towards assigned task
        if task is not None and task.target != position:
            return [direction_towards(position, task.target)]

        # Default fallback: move towards empty tile near shed if holding seeds
        if self._has_viable_seeds(state):
            empty_near_shed = prioritize_unlocked_tiles_by_shed_proximity(
                state.tiles,
                shed_tiles,
                predicate=lambda t: t.kind is None,
            )
            if empty_near_shed and (empty_near_shed[0].x, empty_near_shed[0].y) != position:
                return [direction_towards(position, (empty_near_shed[0].x, empty_near_shed[0].y))]

        return ["PASS"]

    def _market_orders(self, state: NormalizedState) -> list[list[Any]]:
        orders: list[list[Any]] = []

        # 1. Sell all inventory stored in shed
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

        # 2. Expand land if we have excess money and unbought quadrants
        if len(state.unlocked_quadrants) < 4 and state.money >= 2000 and state.day <= 20:
            orders.append(["BUY_LAND"])

        # 3. Buy seeds dynamically based on ROI engine or preferred crop
        chosen_crop = self.config.crop or best_crop_to_plant(
            state, min_budget=self.config.reserve_cash
        )
        if chosen_crop:
            spec = CROPS_SPEC[chosen_crop]
            seed_cost = int(spec["seed"])
            current_seeds = state.seeds.get(chosen_crop, 0)
            needed = max(0, self.config.seed_batch - current_seeds)
            affordable = max(0, int((state.money - self.config.reserve_cash) // seed_cost))
            buy_qty = min(needed, affordable)
            if buy_qty > 0:
                orders.append(["BUY_SEED", chosen_crop, buy_qty])

        # 4. Hire farm hands when pending work is high and cost is low
        pending_work = sum(
            tile.kind == "WEED"
            or (tile.kind == "PLANT" and not tile.watered_today)
            or (tile.kind is None and self._has_viable_seeds(state))
            for tile in state.tiles
        )
        if (
            self.config.enable_hands
            and state.hour == 0
            and state.hires_today == 0
            and pending_work >= 4
            and state.money > self.config.reserve_cash + 50
        ):
            orders.append(["HIRE"])

        return orders[: self.config.max_orders]

    def _closing(self, state: NormalizedState) -> bool:
        return state.day >= 28

    def _has_viable_seeds(self, state: NormalizedState) -> bool:
        for crop, count in state.seeds.items():
            if count > 0 and state.day <= calculate_closing_day(crop):
                return True
        return False

    def _select_seed_to_plant(self, state: NormalizedState) -> str | None:
        # Prioritize seeds in inventory with highest ROI
        viable_crops = [
            crop
            for crop, count in state.seeds.items()
            if count > 0 and state.day <= calculate_closing_day(crop)
        ]
        if not viable_crops:
            return None
        # Pick the best crop
        return viable_crops[0]

    @staticmethod
    def _direction(source: tuple[int, int], target: tuple[int, int]) -> str:
        return direction_towards(source, target)

    @staticmethod
    def _distance(first: tuple[int, int], second: tuple[int, int]) -> int:
        return abs(first[0] - second[0]) + abs(first[1] - second[1])

    @staticmethod
    def _shed_tiles(state: NormalizedState) -> tuple[tuple[int, int], ...]:
        return state.shed_tiles()

    @staticmethod
    def _ripe(tile: Tile, state: NormalizedState) -> bool:
        if tile.kind == "PLANT" and tile.yield_units > 0 and tile.crop:
            spec = CROPS_SPEC.get(tile.crop)
            first_yield = int(spec["first_yield_day"]) if spec else 2
            if tile.planted_day is not None and state.day - tile.planted_day >= first_yield:
                return True
        if tile.animal is not None and tile.yield_units > 0:
            return True
        return False
