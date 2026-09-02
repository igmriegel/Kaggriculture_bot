"""Leader V9: High-Margin Crops, Diversified Livestock & Smart Watering.

Otimizações principais:
1. Labor-Cost ROI Adjuster: Adiciona o custo de fricção operacional (ações de
   trabalho) na estimativa de ROI.
2. Smart Watering: Ignora rega de plantas que não amadurecerão a tempo.
3. Livestock Prioritization: Compra de animais colocada antes de sementes.
4. Goose/Egg Support: Suporte dinâmico para Gansos com base nas demandas.
"""

from dataclasses import dataclass
from typing import Any

from agent.core.state import NormalizedState
from agent.domain.economics import SHOPS, marginal_sale_values
from agent.engines.leader_v2 import ProductionGoal, Task
from agent.engines.leader_v6 import (
    _CROP_BASE_PRICES,
    _CROP_MATURITY,
    _PRODUCTS,
)
from agent.engines.leader_v7 import LeaderV7Engine
from agent.engines.leader_v8 import LeaderV8Config, LeaderV8Engine
from agent.engines.leader_v9 import LeaderV9Config, LeaderV9Engine

_V9_ANIMAL_COST = {"COW": 400, "SHEEP": 500, "GOOSE": 300}


@dataclass(frozen=True)
class V10Config(LeaderV9Config):
    """Configurable genes for genetic algorithm optimization."""

    # Closing parameters
    closing_day: int = 26
    closing_maintenance_threshold: int = 10
    closing_workers_max: int = 5
    closing_workers_min: int = 3
    closing_workers_mid: int = 3
    closing_mid_threshold: int = 5
    # Base allocations
    max_allocatable_slots_base: int = 6
    max_allocatable_slots_multiplier: float = 2.0
    # Animal parameters
    min_cash_buffer_livestock: int = 638
    double_animal_buy_threshold: int = 1878
    # ROI multipliers
    melon_roi_cutoff_day: int = 15
    melon_roi_multiplier: float = 1.7519446856565386
    strawberry_roi_cutoff_day: int = 12
    strawberry_roi_multiplier: float = 1.5178768214982015
    # Market deal parameters
    melon_deal_price: int = 85
    strawberry_deal_price: int = 115
    # Sprint 2: Market Speculation
    speculation_hold_threshold: float = 0.7395195641995185
    speculation_min_liquidity: int = 1640
    # Sprint 3: Anti-Monopoly
    opponent_crop_penalty: float = 0.027970972369217757

    # --- New 14 parameters ---
    # 1. Hires & Workload
    feed_buffer_threshold: int = 4
    feed_buy_min_money: int = 150
    feed_buffer_days: int = 2
    hire_workload_threshold: int = 12
    hire_min_animals: int = 3

    # 2. Land Expansion
    land_unlock_saturation_ratio: float = 0.75
    seed_buffer_per_tile: int = 30

    # 3. Livestock Ratios
    animal_cow_sheep_ratio: float = 3.0
    animal_sheep_cow_ratio: float = 2.0

    # 4. Shed & Sales Prices
    wheat_feed_buffer_per_animal: int = 2
    max_fertilizer_to_keep: int = 3
    front_run_opponent_harvest_threshold: int = 6
    clearance_day_threshold: int = 28
    continuous_sale_min_amount: int = 2
    marginal_sale_price_ratio_floor: float = 0.45


class LeaderV10Engine(LeaderV9Engine):
    """
    Tenth generation engine.
    Parameterizes heuristics into V10Config for evolutionary optimization (Genetic Algorithm).
    Inherits V9 core and features intelligent closing scaling and dynamic crop capping.
    """

    def __init__(self, config: V10Config | None = None) -> None:
        self.v10_config = config or V10Config()
        super().__init__(self.v10_config)

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
            min(8, self.v10_config.max_animals)
            if opp_animals >= 10
            else self.v10_config.max_animals
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
        max_allocatable_slots = max(
            self.v10_config.max_allocatable_slots_base,
            int(self.v10_config.max_allocatable_slots_multiplier * total_workers),
        )
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
            base_roi = max(0.0, base_roi - labor_friction_penalty)
        elif crop == "CARROT":
            labor_friction_penalty = 6.0
            base_roi = max(0.0, base_roi - labor_friction_penalty)
        elif crop == "STRAWBERRY" and state.day < self.v10_config.strawberry_roi_cutoff_day:
            # Boost strawberry early game ROI to accelerate capital accumulation
            base_roi = base_roi * self.v10_config.strawberry_roi_multiplier
        elif crop == "MELON" and state.day < self.v10_config.melon_roi_cutoff_day:
            # Boost melon early/mid game ROI
            base_roi = base_roi * self.v10_config.melon_roi_multiplier

        # Sprint 3: Anti-Monopoly Crop Penalty
        opp_count = sum(1 for t in state.opponent_tiles if t.kind == "PLANT" and t.crop == crop)
        if opp_count > 0:
            penalty = opp_count * self.v10_config.opponent_crop_penalty
            base_roi = base_roi * max(0.0, 1.0 - penalty)

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
        # Handle closing mode
        if state.day >= self.v10_config.closing_day:
            from agent.domain.economics import projected_prices

            projected = projected_prices(
                state.market_inventory, state.shops, state.step, max(0, 720 - state.step)
            )
            orders = self._sales(state, projected)

            total_workers = 1 + len(state.hand_positions)
            active_animals = self._animal_count(state) + self._pending_animals(state)
            plant_count = sum(1 for t in state.tiles if t.kind == "PLANT")

            cost = self._hire_cost(state.hires_today)

            if (active_animals > 0 or plant_count > 0) and state.money >= cost + 150:
                target_workers = (
                    self.v10_config.closing_workers_max
                    if (
                        active_animals + plant_count > self.v10_config.closing_maintenance_threshold
                    )
                    else (
                        self.v10_config.closing_workers_mid
                        if (active_animals + plant_count > self.v10_config.closing_mid_threshold)
                        else self.v10_config.closing_workers_min
                    )
                )
                if (
                    state.day < 29
                    and total_workers < target_workers
                    and len(orders) < self.v10_config.max_orders
                ):
                    orders.append(["HIRE"])

            return orders[: self.v10_config.max_orders]

        if state.day == 0:
            if state.hour == 1 and not self._animal_count(state) and not any(state.shed.values()):
                has_strawberry_shop = any("STRAWBERRY" in SHOPS.get(s, ()) for s in state.shops)
                strawberry_seeds = 3 if has_strawberry_shop else 2
                melon_seeds = 2 if has_strawberry_shop else 3
                return [
                    ["HIRE"],
                    ["BUY_ANIMAL", "COW", 2],
                    ["BUY_ANIMAL", "SHEEP", 1],
                    ["BUY_SEED", "WHEAT", 4],
                    ["BUY_SEED", "MELON", melon_seeds],
                    ["BUY_SEED", "STRAWBERRY", strawberry_seeds],
                ]
            return []

        # Get base orders from LeaderV7Engine
        orders = LeaderV7Engine._build_market_orders(self, state, goals, tasks)
        spending = max(0, state.money - 20)

        # 1. Pure Workload & Liquidity Driven Worker Hiring
        total_workers = 1 + len(state.hand_positions)
        no_hire_yet = not any(o[0] == "HIRE" for o in orders)
        if total_workers < 2 and len(orders) < self.v10_config.max_orders and no_hire_yet:
            unwatered_crops = sum(
                1 for t in state.tiles if t.kind == "PLANT" and not t.watered_today
            )
            unfed_animals = sum(
                1 for t in state.tiles if t.kind == "PASTURE" and t.animal and not t.fed_today
            )
            harvestable = sum(
                1 for t in state.tiles if t.kind == "PLANT" and t.yield_units and t.yield_units > 0
            )
            pending_actions = unwatered_crops + unfed_animals + harvestable

            # Market Feed Purchasing (dynamic feed buffer)
            wheat_in_shed = state.shed.get("WHEAT", 0)
            animal_cnt = self._animal_count(state)
            if (
                animal_cnt > 0
                and wheat_in_shed < self.v10_config.feed_buffer_threshold
                and state.money >= self.v10_config.feed_buy_min_money
            ):
                need_wheat = self.v10_config.feed_buffer_threshold - wheat_in_shed
                orders.append(["BUY_SEED", "WHEAT", need_wheat])

            # Dynamic liquidity buffer: hire cost ($500) + X days animal feed + seed capital
            animal_count = self._animal_count(state)
            wheat_price = max(1, int(state.prices.get("WHEAT", 25)))
            required_feed_buffer = animal_count * self.v10_config.feed_buffer_days * wheat_price
            dynamic_hire_threshold = (
                500 + required_feed_buffer + self.v10_config.min_liquidity_buffer
            )

            # Only hire if workload exceeds single-worker capacity and we have full liquidity
            if pending_actions >= self.v10_config.hire_workload_threshold or (
                animal_count >= self.v10_config.hire_min_animals
                and state.money >= dynamic_hire_threshold
            ):
                if state.money >= dynamic_hire_threshold:
                    orders.append(["HIRE"])

        # 2. Pure Dynamic Land Expansion
        unlocked_count = len(state.unlocked_quadrants)
        no_unlock_yet = not any(o[0] == "BUY_LAND" for o in orders)
        if unlocked_count < 4 and len(orders) < self.v10_config.max_orders and no_unlock_yet:
            occupied_tiles = sum(1 for t in state.tiles if t.kind in ("PLANT", "PASTURE"))
            total_unlocked_capacity = unlocked_count * 9
            saturation_ratio = occupied_tiles / max(1, total_unlocked_capacity)

            # Dynamic liquidity buffer for land purchase: unlock cost ($250) + seed buffer + feed buffer
            animal_count = self._animal_count(state)
            wheat_price = max(1, int(state.prices.get("WHEAT", 25)))
            required_seed_buffer = (
                occupied_tiles * self.v10_config.seed_buffer_per_tile
                + animal_count * self.v10_config.feed_buffer_days * wheat_price
            )
            dynamic_unlock_threshold = (
                250 + required_seed_buffer + self.v10_config.min_liquidity_buffer
            )

            # Unlock when land saturation >= threshold AND we have liquidity to seed the new land
            if (
                saturation_ratio >= self.v10_config.land_unlock_saturation_ratio
                and state.money >= dynamic_unlock_threshold
            ):
                orders.append(["BUY_LAND"])

        # 3. Shop-Aware Livestock Selection
        melon_price = state.prices.get("MELON", 250)
        strawberry_price = state.prices.get("STRAWBERRY", 120)
        has_deal = (melon_price < self.v10_config.melon_deal_price) or (
            strawberry_price < self.v10_config.strawberry_deal_price
        )
        is_early_game = state.day in {1, 2}

        cattle_orders: list[list[Any]] = []
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
                next_animal = (
                    "COW"
                    if current_cows <= current_sheep * self.v10_config.animal_cow_sheep_ratio
                    else "SHEEP"
                )
            elif dairy_shops == 0:
                next_animal = (
                    "SHEEP"
                    if current_sheep <= current_cows * self.v10_config.animal_sheep_cow_ratio
                    else "COW"
                )
            else:
                next_animal = "COW" if current_cows <= current_sheep else "SHEEP"

            cost = _V9_ANIMAL_COST[next_animal]

            # Preserve a minimum seed and hiring buffer when buying livestock
            if (
                state.money - 2 * cost >= self.v10_config.min_cash_buffer_livestock
                and state.money > self.v10_config.double_animal_buy_threshold
            ):
                cattle_orders.append(["BUY_ANIMAL", next_animal, 2])
                spending -= 2 * cost
            elif state.money - cost >= self.v10_config.min_cash_buffer_livestock:
                cattle_orders.append(["BUY_ANIMAL", next_animal, 1])
                spending -= cost

        # Filter out BUY_ANIMAL from base_orders and combine
        filtered_base_orders = [o for o in orders if o[0] != "BUY_ANIMAL"]
        final_orders = cattle_orders + filtered_base_orders

        return final_orders[: self.v10_config.max_orders]

    def _sales(
        self, state: NormalizedState, projected: dict[str, int] | None = None
    ) -> list[list[Any]]:
        orders: list[list[Any]] = []
        is_closing = self._closing(state)
        capacity_pressure = sum(state.shed.values()) >= (
            state.shed_capacity - self.v10_config.shed_safety_buffer
        )
        low_liquidity = state.money < self.v10_config.liquidity_cash_floor

        # Detect Imminent Opponent Harvests for Front-Running
        opp_imminent_harvests = self._detect_opp_imminent_harvests(state)

        regrowable_count = sum(
            1 for t in state.tiles if t.kind == "PLANT" and t.crop in ("STRAWBERRY", "TOMATO")
        )

        # Calculate feed buffer
        total_animals = (
            self._animal_count(state)
            + self._pending_animals(state)
            + sum(1 for inv in state.unit_inventories for k in _V9_ANIMAL_COST if inv.get(k, 0))
        )
        needed_wheat = total_animals * self.v10_config.wheat_feed_buffer_per_animal

        for item, amount in sorted(state.shed.items()):
            if amount <= 0 or item not in _PRODUCTS:
                continue

            if item == "WHEAT" and not is_closing:
                sellable = max(0, amount - needed_wheat)
            elif item == "FERTILIZER" and not is_closing:
                if low_liquidity or regrowable_count == 0:
                    sellable = amount
                else:
                    fert_to_keep = min(
                        self.v10_config.max_fertilizer_to_keep, regrowable_count, amount
                    )
                    sellable = max(0, amount - fert_to_keep)
            else:
                sellable = amount

            if sellable <= 0:
                continue

            # Front-Running Vector: If opponent will harvest this item within 24h, sell NOW
            if (
                opp_imminent_harvests.get(item, 0)
                >= self.v10_config.front_run_opponent_harvest_threshold
                and not is_closing
            ):
                orders.append(["SELL", item, sellable])
                continue

            # Closing, capacity pressure, low liquidity, or Day >= threshold final clearance
            if (
                is_closing
                or capacity_pressure
                or low_liquidity
                or state.day >= self.v10_config.clearance_day_threshold
            ):
                orders.append(["SELL", item, sellable])
                continue

            # Continuous high-margin sales
            if (
                item in {"MILK", "WOOL", "STRAWBERRY", "TOMATO"}
                and amount >= self.v10_config.continuous_sale_min_amount
            ):
                orders.append(["SELL", item, sellable])
                continue

            # Marginal quote threshold check
            values = marginal_sale_values(
                item,
                state.market_inventory.get(item, 10_000),
                sellable,
                opponent_buffer=self.v10_config.opponent_market_buffer,
            )
            base = state.prices.get(item, _CROP_BASE_PRICES.get(item, 25))
            units_to_sell = sum(
                1 for val in values if val >= base * self.v10_config.marginal_sale_price_ratio_floor
            )
            if units_to_sell > 0:
                orders.append(["SELL", item, units_to_sell])

        # Sprint 2: Market Speculation override
        final_orders = []
        for o in orders:
            op, item, qty = o[0], o[1], o[2]
            if (
                op == "SELL"
                and projected
                and item in projected
                and item in state.prices
                and not is_closing
            ):
                expected_price = projected[item]
                current_price = state.prices[item]
                if (
                    current_price < expected_price * self.v10_config.speculation_hold_threshold
                    and state.money > self.v10_config.speculation_min_liquidity
                ):
                    continue
            final_orders.append(o)

        return final_orders
