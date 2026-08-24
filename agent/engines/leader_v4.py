"""Dynamic high-performance market-aware planner (Leader V4).

Inspired by the top-performing playstyle of the competition leader while
maintaining dynamic, market-driven decision making without hardcoded static sequences.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Any

from agent.core.contracts import Action
from agent.core.state import NormalizedState
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

_CROP_MATURITY = {"WHEAT": 2, "CARROT": 2, "TOMATO": 8, "STRAWBERRY": 10, "MELON": 10}
_CROP_BASE_PRICES = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120, "MELON": 250}
_V4_SEED_COST = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}


def _any_inventory(inventory: dict[str, int]) -> bool:
    """Allow any worker to perform tasks that don't depend on inventory contents."""
    del inventory
    return True


def _can_collect_or_harvest(inventory: dict[str, int]) -> bool:
    """Workers can harvest and collect products if they are not holding an unplaced animal."""
    return not any(k in _ANIMAL_COST for k in inventory)


@dataclass(frozen=True)
class LeaderV4Config(LeaderV2Config):
    """Configuration for the dynamic Leader V4 engine."""

    max_animals: int = 18
    target_hands_midgame: int = 12
    shed_safety_buffer: int = 6
    opponent_market_buffer: int = 1


class LeaderV4Engine(LeaderV2Engine):
    """Dynamic, adaptive engine that optimizes crop and livestock portfolios.

    Selects actions based on market signals and expected value without hardcoding.
    """

    def __init__(self, config: LeaderV4Config | None = None) -> None:
        super().__init__(config or LeaderV4Config())
        self.v4_config = config or LeaderV4Config()
        self.cycle_memory = CycleMemory()
        self._last_assignments: list[dict[str, Any]] = []

    def reset_cycle(self) -> None:
        self.cycle_memory.reset_for_episode()

    def act(self, observation: dict[str, Any]) -> dict[str, Any]:
        state = NormalizedState.from_observation(observation)
        self.cycle_memory.begin(state)
        goals = self._goals(state)
        tasks = self._tasks(state, goals)
        commands = self._allocate(state, tasks)
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

        # 1. Dynamic Livestock goals (Cow & Sheep) based on expected ROI
        quadrants = len(state.unlocked_quadrants)
        max_pastures = 4 if quadrants == 1 else (8 if quadrants == 2 else 12)

        # Check animal EV
        cow_ev = self._calculate_animal_ev("COW", state, horizon)
        sheep_ev = self._calculate_animal_ev("SHEEP", state, horizon)

        current_animals = self._animal_count(state) + self._pending_animals(state)
        if horizon < 8 or (cow_ev <= 0 and sheep_ev <= 0):
            target_animals = current_animals
        else:
            # We want to grow livestock sustainably as long as EV is positive
            target_animals = min(max_pastures, self.v4_config.max_animals)

        goals: list[ProductionGoal] = [
            ProductionGoal("operational_animals", target_animals, state.day + 3)
        ]

        # 2. Dynamic Crop goals
        crop_plan = self._dynamic_crop_portfolio(state, horizon, empty)
        for crop, qty in crop_plan:
            if qty > 0:
                goals.append(ProductionGoal(f"plant_{crop.lower()}", qty, state.day + 1))

        return tuple(goals)

    def _calculate_animal_ev(self, animal: str, state: NormalizedState, horizon: int) -> float:
        """Calculate expected net profit from buying an animal now."""
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

        expected_profit = (product_rev + fert_rev) - (cost + feed_cost)
        return expected_profit

    def _dynamic_crop_portfolio(
        self, state: NormalizedState, horizon: int, empty_slots: int
    ) -> list[tuple[str, int]]:
        if empty_slots <= 0 or horizon < 2:
            return []

        # Early game opening (Day 0-3): High value Melon + Wheat combo for big Day 10 cashout
        if state.day <= 3:
            melon_qty = min(11, empty_slots)
            wheat_qty = max(0, min(empty_slots - melon_qty, 6))
            res = [("MELON", melon_qty)]
            if wheat_qty > 0:
                res.append(("WHEAT", wheat_qty))
            return res

        # Evaluate expected value (EV) per tile-day for each crop candidate
        candidates = ["WHEAT", "CARROT", "STRAWBERRY", "MELON"]
        scored: list[tuple[float, str]] = []
        for crop in candidates:
            maturity = _CROP_MATURITY[crop]
            if maturity > horizon:
                continue

            price = state.prices.get(crop, _CROP_BASE_PRICES[crop])
            demand = state.demand.get(crop, 0)
            seed_cost = _V4_SEED_COST[crop]

            if crop == "STRAWBERRY":
                cycles = max(1, (horizon - 10) // 2 + 1) if horizon >= 10 else 1
                est_revenue = price * (cycles * 2) - seed_cost
                eff_maturity = max(maturity, min(horizon, 10 + (cycles - 1) * 2))
            elif crop == "MELON":
                est_revenue = (price * 3) - seed_cost
                eff_maturity = maturity
            elif crop == "WHEAT":
                est_revenue = (price * 2) - seed_cost
                eff_maturity = maturity
            else:  # CARROT
                est_revenue = (price * 2) - seed_cost
                eff_maturity = maturity

            score = (est_revenue / max(1, eff_maturity)) * (1.0 + min(3, demand) * 0.1)
            scored.append((score, crop))

        scored.sort(reverse=True)
        if not scored:
            return [("WHEAT", empty_slots)]

        primary_crop = scored[0][1]
        if len(scored) > 1 and scored[1][0] > scored[0][0] * 0.75:
            secondary_crop = scored[1][1]
            primary_slots = max(1, (empty_slots * 3) // 4)
            secondary_slots = max(0, empty_slots - primary_slots)
            return [(primary_crop, primary_slots), (secondary_crop, secondary_slots)]

        return [(primary_crop, empty_slots)]

    def _tasks(self, state: NormalizedState, goals: tuple[ProductionGoal, ...]) -> list[Task]:
        tasks: list[Task] = []
        opening = state.day == 0

        # 1. Harvest ripe crops and animal products
        for tile in state.tiles:
            point = (tile.x, tile.y)
            if self._ripe(tile, state):
                tasks.append(Task(1, point, ["HARVEST"], _can_collect_or_harvest, ("tile", point)))
                continue

            # 2. Animal care: FEED (priority 2), CARE (priority 3), COLLECT_FERTILIZER (priority 4)
            if tile.animal:
                if not tile.fed_today:
                    tasks.append(Task(2, point, ["FEED"], _has_wheat, ("tile", point)))
                if tile.fertilizer_available:
                    tasks.append(
                        Task(
                            4,
                            point,
                            ["COLLECT_FERTILIZER"],
                            _can_collect_or_harvest,
                            ("tile", point),
                        )
                    )
                elif not tile.cared_today:
                    tasks.append(Task(3, point, ["CARE"], _any_inventory, ("tile", point)))
                continue

            # 3. Water unwatered plants (HIGH PRIORITY and NO inventory restriction)
            if tile.kind == "PLANT" and not tile.watered_today:
                tasks.append(
                    Task(2 if opening else 3, point, ["WATER"], _any_inventory, ("tile", point))
                )

        # 3.5. DIG WEEDS (HIGH PRIORITY 3) - Free up infested tiles immediately
        for tile in state.tiles:
            if tile.kind == "WEED":
                point = (tile.x, tile.y)
                tasks.append(Task(3, point, ["DIG"], _any_inventory, ("tile", point)))

        # 4. Pasture expansion & Animal placement
        target_animals = next((g.quantity for g in goals if g.name == "operational_animals"), 0)
        total_pastures = [t for t in state.tiles if t.kind == "PASTURE"]
        open_pastures = [t for t in total_pastures if not t.animal]

        # Build pasture if open pastures are less than needed to reach target_animals
        build_count = max(0, min(target_animals - len(total_pastures), 2))
        if opening:
            build_count = max(build_count, self.v4_config.opening_animals - len(open_pastures))

        for tile in sorted(
            (t for t in state.tiles if t.kind is None),
            key=lambda t: (self._distance(state.position, (t.x, t.y)), t.y, t.x),
        )[:build_count]:
            point = (tile.x, tile.y)
            tasks.append(
                Task(
                    1 if opening else 4,
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
            point = self._shed_tiles(state)[index % len(self._shed_tiles(state))]
            tasks.append(
                Task(
                    0 if opening else 7,
                    point,
                    ["PICKUP", animal],
                    _can_collect_or_harvest,
                    ("pickup", index),
                )
            )

        # 6. Feed pickups (Wheat from shed to feed animals)
        hungry_animals = sum(1 for tile in state.tiles if tile.animal and not tile.fed_today)
        wheat_in_hands = sum(inv.get("WHEAT", 0) for inv in state.unit_inventories)
        needed_feed_pickups = max(0, hungry_animals - wheat_in_hands)
        feed_pickups = min(len(self._shed_tiles(state)), (needed_feed_pickups + 1) // 2)
        available_wheat = state.shed.get("WHEAT", 0)
        if available_wheat > 0 and feed_pickups:
            reserved_wheat = 0
            for index, point in enumerate(self._shed_tiles(state)[:feed_pickups]):
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

        # 7. Planting tasks based on available seeds
        empty_tiles = [tile for tile in state.tiles if tile.kind is None]
        for crop, count in state.seeds.items():
            if count <= 0:
                continue
            for tile in empty_tiles[:count]:
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
            empty_tiles = empty_tiles[count:]

        # 8. Drop products to shed
        for index, inventory in enumerate(state.unit_inventories):
            if inventory and any(item in _PRODUCTS for item in inventory):
                point = state.units()[index]
                if point in self._shed_tiles(state):
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

    def _build_market_orders(
        self, state: NormalizedState, goals: tuple[ProductionGoal, ...], tasks: list[Task]
    ) -> list[list[Any]]:
        # Day 0 Hour 0: No purchases before hour 1 opening
        if state.day == 0 and state.hour == 0:
            return []

        # 1. Day 0 Hour 1 Opening (Big Bang)
        if state.day == 0 and state.hour == 1:
            return [
                ["HIRE"],
                ["HIRE"],
                ["HIRE"],
                ["HIRE"],
                ["HIRE"],
                ["BUY_ANIMAL", "COW", 1],
                ["BUY_ANIMAL", "SHEEP", 1],
                ["BUY_SEED", "MELON", 11],
                ["BUY_SEED", "WHEAT", 6],
                ["BUY_PRODUCT", "WHEAT", 4],
            ]

        # Early selling to finance setup
        if state.day == 0 and state.hour == 2:
            wheat_stock = state.shed.get("WHEAT", 0)
            if wheat_stock >= 4:
                return [["SELL", "WHEAT", 2]]

        projected = projected_prices(
            state.market_inventory, state.shops, state.step, max(0, 720 - state.step)
        )
        orders = self._sales(state, projected)
        spending = max(0, state.money - 50)

        if self._closing(state):
            return orders[: self.v4_config.max_orders]

        # 2. Strict Animal Feed Purchase: At Hour 0/1 or when out of wheat
        feed_needed = self._animal_feed_deficit(state)
        wheat_price = max(1, int(state.prices.get("WHEAT", 25)))
        if feed_needed > 0 and (state.hour in {0, 1} or state.shed.get("WHEAT", 0) == 0):
            if spending >= wheat_price and len(orders) < self.v4_config.max_orders:
                qty = min(
                    feed_needed, spending // wheat_price, self._market_stock(state, "WHEAT"), 6
                )
                if qty > 0:
                    orders.append(["BUY_PRODUCT", "WHEAT", int(qty)])
                    spending -= qty * wheat_price

        # 3. Livestock expansion (Cow & Sheep)
        animal_goal = next((g.quantity for g in goals if g.name == "operational_animals"), 0)
        current_animals = self._animal_count(state) + self._pending_animals(state)
        if current_animals < animal_goal and self._animal_chain_ready(state):
            next_animal = "COW" if current_animals % 2 == 0 else "SHEEP"
            cost = _ANIMAL_COST[next_animal]
            feed_buffer_cost = 2 * wheat_price
            if spending >= (cost + feed_buffer_cost) and len(orders) < self.v4_config.max_orders:
                orders.append(["BUY_ANIMAL", next_animal, 1])
                spending -= cost

        # 4. Seed purchases based on portfolio goals
        for goal in goals:
            if not goal.name.startswith("plant_") or len(orders) >= self.v4_config.max_orders:
                continue
            crop = goal.name.removeprefix("plant_").upper()
            shortfall = max(0, goal.quantity - state.seeds.get(crop, 0))
            if shortfall <= 0:
                continue
            seed_cost = _V4_SEED_COST.get(crop, 20)
            qty = min(shortfall, spending // seed_cost, self._market_stock(state, crop), 10)
            if qty > 0:
                orders.append(["BUY_SEED", crop, int(qty)])
                spending -= int(qty) * seed_cost

        # 5. Workload-driven Dynamic Hiring (Fibonacci) at Hour 0/1
        if state.hour in {0, 1} and len(orders) < self.v4_config.max_orders:
            productive_tasks = sum(1 for t in tasks if t.priority <= 6)
            if state.money > 10_000:
                target_workers = self.v4_config.target_hands_midgame
            elif state.money > 2_000:
                target_workers = min(8, max(3, (productive_tasks + 1) // 2))
            else:
                target_workers = min(5, max(1, (productive_tasks + 2) // 3))

            current_workers = len(state.units())
            prospective = len(state.hand_positions)

            hires_this_turn = 0
            while (
                current_workers < target_workers
                and len(orders) < self.v4_config.max_orders
                and hires_this_turn < 6
            ):
                hire_cost = self._hire_cost(
                    state.hires_today + prospective - len(state.hand_positions)
                )
                if spending < hire_cost + (wheat_price * 2):
                    break
                orders.append(["HIRE"])
                spending -= hire_cost
                prospective += 1
                current_workers += 1
                hires_this_turn += 1

        # 6. Land expansion (BUY_LAND)
        if (
            state.day >= 5
            and len(state.unlocked_quadrants) < 3
            and len(orders) < self.v4_config.max_orders
            and not self._has_pending_chain(state)
        ):
            land_costs = [1000, 2000, 4000]
            next_cost = land_costs[len(state.unlocked_quadrants) - 1]
            if spending >= next_cost + 400:
                orders.append(["BUY_LAND"])

        return orders[: self.v4_config.max_orders]

    def _sales(
        self, state: NormalizedState, projected: dict[str, int] | None = None
    ) -> list[list[Any]]:
        orders: list[list[Any]] = []
        is_closing = self._closing(state)
        capacity_pressure = sum(state.shed.values()) >= (
            state.shed_capacity - self.v4_config.shed_safety_buffer
        )

        for item, amount in sorted(state.shed.items()):
            if amount <= 0 or item not in _PRODUCTS:
                continue

            if item == "WHEAT" and not is_closing:
                needed_wheat = self._animal_count(state)
                sellable = max(0, amount - needed_wheat)
            else:
                sellable = amount

            if sellable <= 0:
                continue

            # Strategic cashouts
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
                opponent_buffer=self.v4_config.opponent_market_buffer,
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


__all__ = ["LeaderV4Config", "LeaderV4Engine"]
