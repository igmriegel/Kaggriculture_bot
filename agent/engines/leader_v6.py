"""Leader V6: Dynamic livestock and crop portfolio with concentric zoning."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Any

from agent.core.contracts import Action
from agent.core.state import NormalizedState, Tile
from agent.domain.economics import marginal_sale_values, projected_prices
from agent.engines.cycle_memory import CycleMemory
from agent.engines.leader_v2 import (
    _ANIMAL_COST,
    _PRODUCTS,
    LeaderV2Config,
    LeaderV2Engine,
    ProductionGoal,
    Task,
    _has_animal,
    _has_product_for_drop,
    _has_wheat,
)
from agent.engines.spatial_planner import (
    manhattan_distance,
    prioritize_unlocked_tiles_by_shed_proximity,
)

_CROP_MATURITY = {"WHEAT": 2, "CARROT": 2, "TOMATO": 8, "STRAWBERRY": 10, "MELON": 10}
_CROP_BASE_PRICES = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120, "MELON": 250}
_V6_SEED_COST = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}


def _any_inventory(inventory: dict[str, int]) -> bool:
    del inventory
    return True


def _can_collect_or_harvest(inventory: dict[str, int]) -> bool:
    return not any(k in _ANIMAL_COST for k in inventory)


@dataclass(frozen=True)
class LeaderV6Config(LeaderV2Config):
    max_animals: int = 18
    target_hands_midgame: int = 12
    shed_safety_buffer: int = 6
    opponent_market_buffer: int = 1


class LeaderV6Engine(LeaderV2Engine):
    """Next-generation engine combining scale economics with spatial optimization."""

    def __init__(self, config: LeaderV6Config | None = None) -> None:
        self.v6_config = config or LeaderV6Config()
        super().__init__(self.v6_config)
        self.cycle_memory = CycleMemory()
        self._last_assignments: list[dict[str, Any]] = []

    def reset_cycle(self) -> None:
        self.cycle_memory.reset_for_episode()

    def act(self, observation: dict[str, Any]) -> dict[str, Any]:
        state = NormalizedState.from_observation(observation)
        self.cycle_memory.begin(state)
        goals = self._goals(state)
        tasks = self._tasks(state, goals)
        commands = self._allocate_optimal(state, tasks)
        market = self._build_market_orders(state, goals, tasks)
        self.cycle_memory.record_action(state, self._last_assignments, market)
        return Action(
            farmer=commands[0],
            hands=commands[1:],
            market=market,
        ).model_dump()

    def _goals(self, state: NormalizedState) -> tuple[ProductionGoal, ...]:
        horizon = max(0, 30 - state.day)
        empty = self._empty_tiles(state)

        quadrants = len(state.unlocked_quadrants)
        max_pastures = 4 if quadrants == 1 else (8 if quadrants == 2 else 12)

        cow_ev = self._calculate_animal_ev("COW", state, horizon)
        sheep_ev = self._calculate_animal_ev("SHEEP", state, horizon)

        current_animals = self._animal_count(state) + self._pending_animals(state)
        if horizon < 8 or (cow_ev <= 0 and sheep_ev <= 0):
            target_animals = current_animals
        else:
            target_animals = min(max_pastures, self.v6_config.max_animals)

        goals: list[ProductionGoal] = [
            ProductionGoal("operational_animals", target_animals, state.day + 3)
        ]

        crop_plan = self._dynamic_crop_portfolio(state, horizon, empty)
        for crop, qty in crop_plan:
            if qty > 0:
                goals.append(ProductionGoal(f"plant_{crop.lower()}", qty, state.day + 1))

        return tuple(goals)

    def _calculate_animal_ev(self, animal: str, state: NormalizedState, horizon: int) -> float:
        first_yield = 8 if animal == "COW" else 6
        interval = 2 if animal == "COW" else 3
        cost = _ANIMAL_COST.get(animal, 400)
        product = "MILK" if animal == "COW" else "WOOL"

        if horizon <= first_yield:
            return -float(cost)

        productive_days = horizon - first_yield
        cycles = productive_days // interval + 1
        product_price = state.prices.get(product, 160.0 if animal == "COW" else 200.0)
        fert_price = state.prices.get("FERTILIZER", 100.0)
        wheat_price = state.prices.get("WHEAT", 25.0)

        feed_cost = horizon * wheat_price
        product_rev = cycles * product_price
        fert_rev = (horizon // 2) * fert_price

        return (product_rev + fert_rev) - (cost + feed_cost)

    def _dynamic_crop_portfolio(
        self, state: NormalizedState, horizon: int, empty_slots: int
    ) -> list[tuple[str, int]]:
        if empty_slots <= 0 or horizon < 2:
            return []

        candidates = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"]
        scored: list[tuple[float, str]] = []
        for crop in candidates:
            maturity = _CROP_MATURITY[crop]
            if maturity > horizon:
                continue

            price = state.prices.get(crop, _CROP_BASE_PRICES[crop])
            demand = state.demand.get(crop, 0)
            seed_cost = _V6_SEED_COST[crop]

            if crop == "STRAWBERRY":
                cycles = max(1, (horizon - 10) // 2 + 1) if horizon >= 10 else 1
                est_revenue = (price * 2 * cycles) - seed_cost
                eff_maturity = max(maturity, min(horizon, 10 + (cycles - 1) * 2))
            elif crop == "TOMATO":
                cycles = max(1, (horizon - 8) // 1 + 1) if horizon >= 8 else 1
                est_revenue = (price * 1 * cycles) - seed_cost
                eff_maturity = max(maturity, min(horizon, 8 + (cycles - 1) * 1))
            else:
                max_yield = 6 if crop in {"WHEAT", "MELON"} else 4
                est_revenue = (price * max_yield) - seed_cost
                eff_maturity = maturity

            ev_per_day = (est_revenue / max(1, eff_maturity)) * (1.0 + min(demand, 10) * 0.05)
            scored.append((ev_per_day, crop))

        scored.sort(reverse=True)
        if not scored:
            return []

        allocated: list[tuple[str, int]] = []
        remaining_slots = empty_slots

        if (self._animal_count(state) > 0 or state.day == 0) and state.shed.get("WHEAT", 0) < 4:
            wheat_reserved = min(remaining_slots, 6)
            allocated.append(("WHEAT", wheat_reserved))
            remaining_slots -= wheat_reserved

        if remaining_slots <= 0:
            return allocated

        primary_crop = scored[0][1]
        allocated.append((primary_crop, remaining_slots))
        return allocated

    def _tasks(self, state: NormalizedState, goals: tuple[ProductionGoal, ...]) -> list[Task]:
        tasks: list[Task] = []
        opening = state.day == 0
        shed_tiles = state.shed_tiles()

        # 1. Harvest ripe crops and animal products
        for tile in state.tiles:
            point = (tile.x, tile.y)
            if self._ripe(tile, state):
                is_decay_risk = (
                    tile.kind == "PLANT"
                    and tile.max_lifespan_step is not None
                    and state.step >= tile.max_lifespan_step - 48
                )
                harvest_priority = 0 if is_decay_risk else 1
                tasks.append(
                    Task(
                        harvest_priority,
                        point,
                        ["HARVEST"],
                        _can_collect_or_harvest,
                        ("tile", point),
                    )
                )
                continue

            # 2. Animal care: FEED (priority 1), CARE (priority 2), COLLECT_FERTILIZER (priority 3)
            if tile.animal:
                if not tile.fed_today:
                    tasks.append(Task(1, point, ["FEED"], _has_wheat, ("tile", point)))
                if tile.fertilizer_available:
                    tasks.append(
                        Task(
                            3,
                            point,
                            ["COLLECT_FERTILIZER"],
                            _can_collect_or_harvest,
                            ("tile", point),
                        )
                    )
                elif not tile.cared_today:
                    tasks.append(Task(2, point, ["CARE"], _any_inventory, ("tile", point)))
                continue

            # 3. Water plants
            if tile.kind == "PLANT" and not tile.watered_today:
                is_drought_risk = tile.consecutive_unwatered >= 1
                water_priority = 1 if is_drought_risk else (4 if opening else 5)
                tasks.append(
                    Task(water_priority, point, ["WATER"], _any_inventory, ("tile", point))
                )

        # 3.5. Clear weeds
        for tile in state.tiles:
            if tile.kind == "WEED":
                point = (tile.x, tile.y)
                tasks.append(Task(6, point, ["DIG"], _any_inventory, ("tile", point)))

        # 4. Pasture expansion & Animal placement with CONCENTRIC ZONING
        pending = self._pending_animals(state)
        total_pastures = [t for t in state.tiles if t.kind == "PASTURE"]
        open_pastures = [t for t in total_pastures if not t.animal]

        planned_animals = (
            self.v6_config.opening_animals
            if state.day == 0 and state.hour == 1 and not any(state.shed.values())
            else pending
        )
        build_count = max(0, planned_animals - len(open_pastures))

        empty_near_shed = prioritize_unlocked_tiles_by_shed_proximity(
            state.tiles, shed_tiles, predicate=lambda t: t.kind is None
        )
        for tile in empty_near_shed[:build_count]:
            point = (tile.x, tile.y)
            tasks.append(
                Task(
                    1 if opening else 5,
                    point,
                    ["BUILD_PASTURE"],
                    _any_inventory,
                    ("tile", point),
                )
            )

        for tile in open_pastures:
            point = (tile.x, tile.y)
            tasks.append(Task(2 if opening else 6, point, ["PLACE"], _has_animal, ("tile", point)))

        # 5. Shed Animal Pickups
        for index, animal in enumerate(self._shed_animals(state)):
            point = shed_tiles[index % len(shed_tiles)]
            tasks.append(
                Task(
                    0 if opening else 7,
                    point,
                    ["PICKUP", animal],
                    _can_collect_or_harvest,
                    ("pickup", index),
                )
            )

        # 6. Feed pickups (Wheat from shed)
        hungry_animals = sum(1 for tile in state.tiles if tile.animal and not tile.fed_today)
        feed_pickups = min(len(shed_tiles), (hungry_animals + 1) // 2)
        available_wheat = state.shed.get("WHEAT", 0)
        if available_wheat > 0 and feed_pickups:
            reserved_wheat = 0
            for index, point in enumerate(shed_tiles[:feed_pickups]):
                feed_quantity = min(2, max(0, available_wheat - reserved_wheat))
                if not feed_quantity:
                    break
                tasks.append(
                    Task(
                        0,
                        point,
                        ["PICKUP", "WHEAT", feed_quantity],
                        _can_collect_or_harvest,
                        ("wheat", index),
                    )
                )
                reserved_wheat += feed_quantity

        # 7. Planting tasks: Concentric ordering for planting
        empty_for_planting = prioritize_unlocked_tiles_by_shed_proximity(
            state.tiles, shed_tiles, predicate=lambda t: t.kind is None
        )
        for crop, count in state.seeds.items():
            if count <= 0:
                continue
            for tile in empty_for_planting[:count]:
                point = (tile.x, tile.y)
                tasks.append(
                    Task(
                        3 if opening else 8,
                        point,
                        ["PLANT", crop],
                        _any_inventory,
                        ("tile", point),
                    )
                )
            empty_for_planting = empty_for_planting[count:]

        # 8. Drop products to shed
        for index, inventory in enumerate(state.unit_inventories):
            if inventory and any(item in _PRODUCTS for item in inventory):
                point = state.units()[index]
                if point in shed_tiles:
                    preserve_feed = self._animal_count(state) > 0
                    tasks.append(
                        Task(
                            11,
                            point,
                            ["DROP"],
                            partial(_has_product_for_drop, preserve_feed=preserve_feed),
                            ("unit", index),
                        )
                    )

        return [
            task
            for task in tasks
            if not self.cycle_memory.is_blocked(
                state,
                str(task.command[0]),
                task.target,
                task.command[1]
                if len(task.command) > 1 and isinstance(task.command[1], str)
                else None,
            )
        ]

    def _allocate_optimal(self, state: NormalizedState, tasks: list[Task]) -> list[list[Any]]:
        positions = state.units()
        n_units = len(positions)
        inventories = [
            state.unit_inventories[index] if index < len(state.unit_inventories) else {}
            for index in range(n_units)
        ]
        commands: list[list[Any]] = [["PASS"] for _ in positions]
        assignments: list[dict[str, Any]] = []

        if not tasks:
            self._last_assignments = assignments
            return commands

        valid_tasks = sorted(tasks, key=lambda item: item.priority)
        free_units = set(range(n_units))
        reserved_locks: set[tuple[str, object]] = set()

        priority_buckets: dict[int, list[Task]] = {}
        for task in valid_tasks:
            priority_buckets.setdefault(task.priority, []).append(task)

        for p_level in sorted(priority_buckets.keys()):
            tier_tasks = [
                t
                for t in priority_buckets[p_level]
                if not (t.reservation and t.reservation in reserved_locks)
            ]
            if not tier_tasks or not free_units:
                continue

            available_workers = list(free_units)
            cost_matrix: list[list[int]] = []
            for u_idx in available_workers:
                u_pos = positions[u_idx]
                u_inv = inventories[u_idx]
                row: list[int] = []
                for _t_idx, task in enumerate(tier_tasks):
                    if not task.eligible(u_inv):
                        row.append(9999)
                    else:
                        dist = manhattan_distance(u_pos, task.target)
                        row.append(dist)
                cost_matrix.append(row)

            for _ in range(min(len(available_workers), len(tier_tasks))):
                best_cost = 9999
                best_w = -1
                best_t = -1
                for w_i, u_idx in enumerate(available_workers):
                    if u_idx not in free_units:
                        continue
                    for t_i, task in enumerate(tier_tasks):
                        if task.reservation and task.reservation in reserved_locks:
                            continue
                        c = cost_matrix[w_i][t_i]
                        if c < best_cost:
                            best_cost = c
                            best_w = u_idx
                            best_t = t_i

                if best_cost >= 9999 or best_w == -1 or best_t == -1:
                    break

                matched_task = tier_tasks[best_t]
                if positions[best_w] == matched_task.target:
                    commands[best_w] = self._command_for(matched_task, inventories[best_w])
                else:
                    commands[best_w] = [self._direction(positions[best_w], matched_task.target)]

                assignments.append(
                    {
                        "unit_index": best_w,
                        "target": matched_task.target,
                        "command": commands[best_w],
                        "planned_command": matched_task.command,
                    }
                )
                free_units.remove(best_w)
                if matched_task.reservation:
                    reserved_locks.add(matched_task.reservation)

        self._last_assignments = assignments
        return commands

    def _build_market_orders(
        self, state: NormalizedState, goals: tuple[ProductionGoal, ...], tasks: list[Task]
    ) -> list[list[Any]]:
        # Big-bang opening on Day 0 Hour 1
        if state.day == 0:
            if state.hour == 1 and not self._animal_count(state) and not any(state.shed.values()):
                return [
                    ["HIRE"],
                    ["BUY_ANIMAL", "COW", 2],
                    ["BUY_ANIMAL", "SHEEP", 2],
                    ["BUY_SEED", "WHEAT", 4],
                    ["BUY_SEED", "MELON", 4],
                ]
            return []

        projected = projected_prices(
            state.market_inventory, state.shops, state.step, max(0, 720 - state.step)
        )
        orders = self._sales(state, projected)
        spending = max(0, state.money - 20)

        if self._closing(state):
            return orders[: self.v6_config.max_orders]

        # 1. Animal Feed Purchase
        feed_needed = self._animal_feed_deficit(state)
        wheat_price = max(1, int(state.prices.get("WHEAT", 25)))
        if feed_needed > 0 and (state.hour in {0, 1} or state.shed.get("WHEAT", 0) == 0):
            if spending >= wheat_price and len(orders) < self.v6_config.max_orders:
                qty = min(
                    feed_needed, spending // wheat_price, self._market_stock(state, "WHEAT"), 6
                )
                if qty > 0:
                    orders.append(["BUY_PRODUCT", "WHEAT", int(qty)])
                    spending -= qty * wheat_price

        # 2. Dynamic Labor Scaling
        if state.hour in {0, 1} and len(orders) < self.v6_config.max_orders:
            productive_tasks = sum(1 for t in tasks if t.priority <= 6)
            active_animals = self._animal_count(state) + self._pending_animals(state)
            plant_count = sum(1 for t in state.tiles if t.kind == "PLANT")

            base_min = 3 if active_animals > 0 or plant_count > 6 else (2 if plant_count > 0 else 1)
            if state.money > 10_000:
                target_workers = self.v6_config.target_hands_midgame
            elif state.money > 2_000:
                target_workers = min(8, max(base_min, (productive_tasks + 1) // 2))
            else:
                target_workers = min(5, max(base_min, (productive_tasks + 2) // 3))

            current_workers = len(state.units())
            prospective = len(state.hand_positions)

            hires_this_turn = 0
            while (
                current_workers < target_workers
                and len(orders) < self.v6_config.max_orders
                and hires_this_turn < 6
            ):
                cost = self._hire_cost(state.hires_today + prospective - len(state.hand_positions))
                if spending < cost:
                    break
                orders.append(["HIRE"])
                spending -= cost
                prospective += 1
                current_workers += 1
                hires_this_turn += 1

        # 3. Livestock expansion (Cow & Sheep)
        animal_goal = next((g.quantity for g in goals if g.name == "operational_animals"), 0)
        current_animals = self._animal_count(state) + self._pending_animals(state)
        if current_animals < animal_goal and self._animal_chain_ready(state):
            next_animal = "COW" if current_animals % 2 == 0 else "SHEEP"
            cost = _ANIMAL_COST[next_animal]
            feed_buffer_cost = 2 * wheat_price
            if spending >= (cost + feed_buffer_cost) and len(orders) < self.v6_config.max_orders:
                orders.append(["BUY_ANIMAL", next_animal, 1])
                spending -= cost

        # 4. Seed purchases based on portfolio goals
        for goal in goals:
            if not goal.name.startswith("plant_") or len(orders) >= self.v6_config.max_orders:
                continue
            crop = goal.name.removeprefix("plant_").upper()
            shortfall = max(0, goal.quantity - state.seeds.get(crop, 0))
            if shortfall <= 0:
                continue
            seed_cost = _V6_SEED_COST.get(crop, 20)
            qty = min(shortfall, spending // seed_cost, self._market_stock(state, crop), 8)
            if qty > 0:
                orders.append(["BUY_SEED", crop, int(qty)])
                spending -= int(qty) * seed_cost

        # 5. Land expansion (BUY_LAND)
        if (
            state.day >= 5
            and len(state.unlocked_quadrants) < 3
            and len(orders) < self.v6_config.max_orders
            and not self._has_pending_chain(state)
        ):
            land_costs = [1000, 2000, 4000]
            next_cost = land_costs[len(state.unlocked_quadrants) - 1]
            if spending >= next_cost + 400:
                orders.append(["BUY_LAND"])

        return orders[: self.v6_config.max_orders]

    @staticmethod
    def _market_stock(state: NormalizedState, item: str) -> int:
        return state.market_inventory.get(item, 10_000)

    def _sales(
        self, state: NormalizedState, projected: dict[str, int] | None = None
    ) -> list[list[Any]]:
        orders: list[list[Any]] = []
        is_closing = self._closing(state)
        capacity_pressure = sum(state.shed.values()) >= (
            state.shed_capacity - self.v6_config.shed_safety_buffer
        )

        for item, amount in sorted(state.shed.items()):
            if amount <= 0 or item not in _PRODUCTS:
                continue

            if item == "WHEAT" and not is_closing:
                total_animals = (
                    self._animal_count(state)
                    + self._pending_animals(state)
                    + sum(
                        1 for inv in state.unit_inventories for k in _ANIMAL_COST if inv.get(k, 0)
                    )
                )
                needed_wheat = total_animals * 2
                sellable = max(0, amount - needed_wheat)
            else:
                sellable = amount

            if sellable <= 0:
                continue

            if (
                is_closing
                or capacity_pressure
                or item == "MELON"
                or (item in {"MILK", "WOOL", "FERTILIZER"} and amount >= 2)
            ):
                orders.append(["SELL", item, sellable])
                continue

            values = marginal_sale_values(
                item,
                state.market_inventory.get(item, 10_000),
                sellable,
                opponent_buffer=self.v6_config.opponent_market_buffer,
            )
            base = state.prices.get(item, _CROP_BASE_PRICES.get(item, 25))

            units_to_sell = sum(1 for val in values if val >= base * 0.80)
            if units_to_sell > 0:
                orders.append(["SELL", item, units_to_sell])

        return orders

    def _animal_feed_deficit(self, state: NormalizedState) -> int:
        animals = self._animal_count(state)
        if animals == 0:
            return 0
        owned_wheat = state.shed.get("WHEAT", 0) + sum(
            inv.get("WHEAT", 0) for inv in state.unit_inventories
        )
        return max(0, animals - owned_wheat)

    def _animal_chain_ready(self, state: NormalizedState) -> bool:
        unoccupied_pastures = sum(
            1 for t in state.tiles if t.kind == "PASTURE" and t.animal is None
        )
        empty_tiles = sum(1 for t in state.tiles if t.kind is None)
        has_space_or_pasture = (unoccupied_pastures > self._pending_animals(state)) or (
            empty_tiles > 0 and self._pending_animals(state) == 0
        )
        return has_space_or_pasture and sum(state.shed.values()) < (state.shed_capacity - 3)

    def _has_pending_chain(self, state: NormalizedState) -> bool:
        if any(
            self._ripe(tile, state)
            or (tile.animal and not tile.fed_today)
            or (tile.animal and tile.fertilizer_available)
            or (tile.kind == "PLANT" and not tile.watered_today)
            for tile in state.tiles
        ):
            return True
        return sum(state.shed.values()) >= (state.shed_capacity - 10)

    @staticmethod
    def _ripe(tile: Tile, state: NormalizedState) -> bool:
        first_yield = {"WHEAT": 2, "CARROT": 2, "TOMATO": 8, "STRAWBERRY": 10, "MELON": 10}
        if tile.animal and tile.yield_units > 0:
            return True
        if tile.kind == "PLANT" and tile.yield_units > 0:
            if tile.max_lifespan_step is not None and state.step >= tile.max_lifespan_step - 48:
                return True
            if (
                tile.crop in first_yield
                and tile.planted_day is not None
                and state.day - tile.planted_day >= first_yield[tile.crop]
            ):
                return True
        return False
