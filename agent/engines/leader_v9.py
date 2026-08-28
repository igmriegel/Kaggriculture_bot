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
    _PRODUCTS,
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
        total_workers = 1 + len(state.hand_positions)
        # Limit seed allocation to what our workforce can realistically plant and maintain
        max_allocatable_slots = max(6, 2 * total_workers)
        empty_slots = min(self._empty_tiles(state), max_allocatable_slots)

        for _ in range(empty_slots):
            best_crop = None
            best_marginal_roi = -9999.0

            for crop in candidates:
                maturity = _CROP_MATURITY.get(crop, 1)
                if maturity > remaining_days:
                    continue

                # Only enforce WHEAT/CARROT limits if alternative high-value shops are unlocked
                has_high_value_shop = any(
                    any(c in SHOPS.get(shop, ()) for c in ("MELON", "STRAWBERRY", "TOMATO"))
                    for shop in state.shops
                )

                current_planned = existing_crops.get(crop, 0) + allocated.get(crop, 0)
                if has_high_value_shop:
                    if crop == "WHEAT" and current_planned >= 20:
                        continue
                    if crop == "CARROT" and current_planned >= 15:
                        continue

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
        elif crop == "STRAWBERRY" and state.day < 12:
            # Boost strawberry early game ROI to accelerate capital accumulation
            return base_roi * 1.5
        elif crop == "MELON" and state.day < 15:
            # Boost melon early/mid game ROI
            return base_roi * 1.3
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
        # Handle closing mode (Day 26+)
        # We bypass V8/V6 early return but still generate sales and hire a maintenance crew
        if state.day >= 26:
            from agent.domain.economics import projected_prices

            projected = projected_prices(
                state.market_inventory, state.shops, state.step, max(0, 720 - state.step)
            )
            orders = self._sales(state, projected)

            total_workers = 1 + len(state.hand_positions)
            active_animals = self._animal_count(state) + self._pending_animals(state)
            plant_count = sum(1 for t in state.tiles if t.kind == "PLANT")

            cost = self._hire_cost(state.hires_today)

            # Keep a minimum worker crew of 2 (or 3/4 if farm is large) to prevent crops drying/decaying into weeds
            if (active_animals > 0 or plant_count > 0) and state.money >= cost + 150:
                target_workers = (
                    4
                    if (active_animals + plant_count > 12)
                    else (3 if (active_animals + plant_count > 5) else 2)
                )
                if (
                    state.day < 29
                    and total_workers < target_workers
                    and len(orders) < self.v9_config.max_orders
                ):
                    orders.append(["HIRE"])

            return orders[: self.v9_config.max_orders]

        if state.day == 0:
            return super()._build_market_orders(state, goals, tasks)

        # Oportunidade de mercado nos dias 1-2:
        # Se Melão estiver muito barato (< $85) ou Morango (< $115),
        # postergamos o gado para a próxima rodada para focar na lavoura rápida.
        melon_price = state.prices.get("MELON", 250)
        strawberry_price = state.prices.get("STRAWBERRY", 120)
        has_deal = (melon_price < 85) or (strawberry_price < 115)
        is_early_game = state.day in {1, 2}

        cattle_orders: list[list[Any]] = []
        spending = max(0, state.money - 20)

        # 1. Livestock Buying Prioritized (before base seeds consume cash)
        animal_goal = next((g.quantity for g in goals if g.name == "operational_animals"), 0)
        current_animals = self._animal_count(state) + self._pending_animals(state)

        if (
            current_animals < animal_goal
            and self._animal_chain_ready(state)
            and not (is_early_game and has_deal)
        ):
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

    def _sales(
        self, state: NormalizedState, projected: dict[str, int] | None = None
    ) -> list[list[Any]]:
        orders: list[list[Any]] = []
        is_closing = self._closing(state)

        # Calculate feed buffer
        total_animals = (
            self._animal_count(state)
            + self._pending_animals(state)
            + sum(1 for inv in state.unit_inventories for k in _V9_ANIMAL_COST if inv.get(k, 0))
        )
        needed_wheat = total_animals * 2

        for item, amount in sorted(state.shed.items()):
            if amount <= 0 or item not in _PRODUCTS:
                continue

            if item == "WHEAT" and not is_closing:
                sellable = max(0, amount - needed_wheat)
            elif item == "FERTILIZER" and not is_closing:
                regrowable_count = sum(
                    1
                    for t in state.tiles
                    if t.kind == "PLANT" and t.crop in ("STRAWBERRY", "TOMATO")
                )
                if regrowable_count == 0 or state.money < 150:
                    sellable = amount
                else:
                    fert_to_keep = min(3, regrowable_count, amount)
                    sellable = max(0, amount - fert_to_keep)
            else:
                sellable = amount

            if sellable > 0:
                orders.append(["SELL", item, sellable])

        return orders
