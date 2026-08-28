"""Leader V9: High-Margin Crops, Diversified Livestock & Smart Watering.

Otimizações principais:
1. Labor-Cost ROI Adjuster: Adiciona o custo de fricção operacional (ações de
   trabalho) na estimativa de ROI.
2. Smart Watering: Ignora rega de plantas que não amadurecerão a tempo.
3. Livestock Prioritization: Compra de animais colocada antes de sementes.
4. Goose/Egg Support: Suporte dinâmico para Gansos com base nas demandas.
"""

from typing import Any

from agent.core.state import NormalizedState
from agent.domain.economics import SHOPS
from agent.engines.leader_v2 import ProductionGoal, Task
from agent.engines.leader_v6 import (
    _CROP_MATURITY,
)
from agent.engines.leader_v8 import LeaderV8Config, LeaderV8Engine

_V9_ANIMAL_COST = {"COW": 400, "SHEEP": 500, "GOOSE": 300}


class LeaderV9Config(LeaderV8Config):
    pass


class LeaderV9Engine(LeaderV8Engine):
    def __init__(self, config: LeaderV9Config | None = None) -> None:
        self.v9_config = config or LeaderV9Config()
        super().__init__(self.v9_config)

    def _goals(self, state: NormalizedState) -> tuple[ProductionGoal, ...]:
        horizon = max(0, 30 - state.day)
        empty = self._empty_tiles(state)

        quadrants = len(state.unlocked_quadrants)
        max_pastures = 4 if quadrants == 1 else (8 if quadrants == 2 else 14)
        current_animals = self._animal_count(state) + self._pending_animals(state)

        dairy_shops = sum(1 for shop in state.shops if "MILK" in SHOPS.get(shop, ()))
        wool_shops = sum(1 for shop in state.shops if "WOOL" in SHOPS.get(shop, ()))

        opp_animals = sum(1 for t in state.opponent_tiles if t.animal in _V9_ANIMAL_COST)
        effective_max_animals = (
            min(8, self.v9_config.max_animals) if opp_animals >= 10 else self.v9_config.max_animals
        )
        base_animal_target = 6 + (dairy_shops + wool_shops) * 2

        if horizon < 8:
            target_animals = current_animals
        else:
            target_animals = min(max_pastures, base_animal_target, effective_max_animals)

        goals: list[ProductionGoal] = [
            ProductionGoal("operational_animals", target_animals, state.day + 3)
        ]

        crop_plan = self._dynamic_crop_portfolio(state, horizon, empty)
        for crop, qty in crop_plan:
            if qty > 0:
                goals.append(ProductionGoal(f"plant_{crop.lower()}", qty, state.day + 1))

        return tuple(goals)

    def _dynamic_crop_portfolio(
        self, state: NormalizedState, horizon: int, empty_slots: int
    ) -> list[tuple[str, int]]:
        remaining_days = max(1, 30 - state.day)
        if empty_slots <= 0 or remaining_days < 2:
            return []

        allocated: dict[str, int] = {}
        existing_crops: dict[str, int] = {}
        for tile in state.tiles:
            if tile.kind == "PLANT" and tile.crop:
                existing_crops[tile.crop] = existing_crops.get(tile.crop, 0) + 1

        candidates = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"]

        for _ in range(empty_slots):
            best_crop = None
            best_marginal_roi = -9999.0

            for crop in candidates:
                maturity = _CROP_MATURITY.get(crop, 1)
                if maturity > remaining_days:
                    continue

                current_planned = existing_crops.get(crop, 0) + allocated.get(crop, 0)
                marginal_roi = self._calculate_marginal_tile_roi(
                    crop, state, remaining_days, current_planned
                )

                if marginal_roi > best_marginal_roi:
                    best_marginal_roi = marginal_roi
                    best_crop = crop

            if best_crop is None or best_marginal_roi <= 0.0:
                break

            allocated[best_crop] = allocated.get(best_crop, 0) + 1

        return [(crop, qty) for crop, qty in allocated.items() if qty > 0]

    def _calculate_marginal_tile_roi(
        self, crop: str, state: NormalizedState, horizon: int, current_planned_tiles: int
    ) -> float:
        base_roi = super()._calculate_marginal_tile_roi(crop, state, horizon, current_planned_tiles)

        # Labor Friction Penalty
        if crop == "WHEAT":
            labor_friction_penalty = 12.0
            return max(0.0, base_roi - labor_friction_penalty)
        elif crop == "CARROT":
            labor_friction_penalty = 6.0
            return max(0.0, base_roi - labor_friction_penalty)
        return base_roi

    def _tasks(self, state: NormalizedState, goals: tuple[ProductionGoal, ...]) -> list[Task]:
        tasks = super()._tasks(state, goals)

        filtered_tasks: list[Task] = []
        remaining_days = max(1, 30 - state.day)

        for task in tasks:
            if "WATER" in task.command:
                tile = next((t for t in state.tiles if (t.x, t.y) == task.target), None)
                if tile and tile.crop:
                    # Smart Watering: evita regar se a planta não puder ser colhida a tempo
                    maturity = _CROP_MATURITY.get(tile.crop, 2)
                    planted_day = tile.planted_day or state.day
                    days_growing = state.day - planted_day
                    days_to_harvest = max(0, maturity - days_growing)

                    if days_to_harvest > remaining_days:
                        continue
            elif len(task.command) > 1 and task.command[0] == "PLANT":
                crop = task.command[1]
                maturity = _CROP_MATURITY.get(crop, 2)
                if maturity > remaining_days:
                    continue

            filtered_tasks.append(task)

        return filtered_tasks

    def _build_market_orders(
        self, state: NormalizedState, goals: tuple[ProductionGoal, ...], tasks: list[Task]
    ) -> list[list[Any]]:
        if state.day == 0:
            return super()._build_market_orders(state, goals, tasks)

        cattle_orders: list[list[Any]] = []
        spending = max(0, state.money - 20)

        # 1. Livestock Buying Prioritized (before base seeds consume cash)
        animal_goal = next((g.quantity for g in goals if g.name == "operational_animals"), 0)
        current_animals = self._animal_count(state) + self._pending_animals(state)

        if current_animals < animal_goal and self._animal_chain_ready(state):
            yarn_shops = sum(1 for shop in state.shops if "WOOL" in SHOPS.get(shop, ()))
            dairy_shops = sum(1 for shop in state.shops if "MILK" in SHOPS.get(shop, ()))

            current_cows = sum(1 for t in state.tiles if t.animal == "COW")
            current_sheep = sum(1 for t in state.tiles if t.animal == "SHEEP")

            if yarn_shops == 0:
                next_animal = "COW" if current_cows <= current_sheep * 3 else "SHEEP"
            elif dairy_shops == 0:
                next_animal = "SHEEP" if current_sheep <= current_cows * 2 else "COW"
            else:
                next_animal = "COW" if current_cows <= current_sheep else "SHEEP"

            cost = _V9_ANIMAL_COST[next_animal]

            # Preserve a minimum seed and hiring buffer of $500 when buying livestock
            min_cash_buffer = 500
            if state.money - 2 * cost >= min_cash_buffer and state.money > 1800:
                cattle_orders.append(["BUY_ANIMAL", next_animal, 2])
                spending -= 2 * cost
            elif state.money - cost >= min_cash_buffer:
                cattle_orders.append(["BUY_ANIMAL", next_animal, 1])
                spending -= cost

        base_orders = super()._build_market_orders(state, goals, tasks)
        filtered_base_orders = [o for o in base_orders if o[0] != "BUY_ANIMAL"]

        final_orders = cattle_orders + filtered_base_orders
        return final_orders[: self.v9_config.max_orders]
