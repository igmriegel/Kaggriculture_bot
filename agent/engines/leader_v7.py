"""Leader V7: Market-Aware Dynamic Portfolio Engine (Built on LeaderV6).

Builds directly on top of LeaderV6 (concentric spatial zoning, optimal bipartite worker matching,
high-velocity livestock pipeline, robust cash flow management) and introduces dynamic market-aware
intelligence:
1. Dynamic Crop Selection: Enhances V6 crop scoring with live town shop consumption
   drainage rates and opponent planted crop supply forecasting.
2. Dynamic Livestock Management: Opponent animal fleet tracking to adjust livestock targets.
3. Active Fertilizer Application: Fertilizes regrowable crops (Strawberry/Tomato) for 2x yield
   instead of immediately selling all fertilizer.
4. Quad 4 Expansion: Supports unlocking up to all 4 quadrants as capital allows.
5. Marginal Price Selling: Uses dynamic projected prices and marginal curves.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent.core.state import NormalizedState
from agent.domain.economics import SHOPS, marginal_sale_values
from agent.domain.roi import calculate_dynamic_harvest_price, estimate_opponent_expected_harvests
from agent.engines.leader_v2 import ProductionGoal, Task
from agent.engines.leader_v6 import (
    _ANIMAL_COST,
    _CROP_BASE_PRICES,
    _CROP_MATURITY,
    _PRODUCTS,
    _V6_SEED_COST,
    LeaderV6Config,
    LeaderV6Engine,
)


def _has_fertilizer(inventory: dict[str, int]) -> bool:
    return inventory.get("FERTILIZER", 0) > 0


@dataclass(frozen=True)
class LeaderV7Config(LeaderV6Config):
    max_animals: int = 18
    target_hands_midgame: int = 12
    shed_safety_buffer: int = 6
    opponent_market_buffer: int = 1
    liquidity_cash_floor: int = 1200
    price_appreciation_threshold: float = 1.08


class LeaderV7Engine(LeaderV6Engine):
    """Evolved LeaderV7 building on proven LeaderV6 foundations with dynamic market intelligence."""

    def __init__(self, config: LeaderV7Config | None = None) -> None:
        self.v7_config = config or LeaderV7Config()
        super().__init__(self.v7_config)

    # ------------------------------------------------------------------
    # 1. Dynamic Goals: Town Demand & Opponent Supply Aware
    # ------------------------------------------------------------------

    def _goals(self, state: NormalizedState) -> tuple[ProductionGoal, ...]:
        horizon = max(0, 30 - state.day)
        empty = self._empty_tiles(state)

        quadrants = len(state.unlocked_quadrants)
        max_pastures = 4 if quadrants == 1 else (8 if quadrants == 2 else 14)

        cow_ev = self._calculate_animal_ev("COW", state, horizon)
        sheep_ev = self._calculate_animal_ev("SHEEP", state, horizon)
        current_animals = self._animal_count(state) + self._pending_animals(state)

        # Detect opponent animal flooding
        opp_animals = sum(1 for t in state.opponent_tiles if t.animal in _ANIMAL_COST)
        effective_max_animals = (
            min(8, self.v7_config.max_animals) if opp_animals >= 10 else self.v7_config.max_animals
        )

        if horizon < 8 or (cow_ev <= 0 and sheep_ev <= 0):
            target_animals = current_animals
        else:
            target_animals = min(max_pastures, effective_max_animals)

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
        if empty_slots <= 0 or horizon < 2:
            return []

        # Count active town shop drain for each product
        town_drain: dict[str, int] = {}
        for shop in state.shops:
            for item in SHOPS.get(shop, ()):
                town_drain[item] = town_drain.get(item, 0) + 1

        # Project opponent supply to detect saturation
        opp_supply = estimate_opponent_expected_harvests(state.opponent_tiles)

        candidates = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"]
        scored: list[tuple[float, str]] = []

        for crop in candidates:
            maturity = _CROP_MATURITY[crop]
            if maturity > horizon:
                continue

            first_harvest_day = min(30, state.day + maturity)
            est_unit_price = calculate_dynamic_harvest_price(crop, state, first_harvest_day)
            seed_cost = _V6_SEED_COST[crop]

            # Town shop drain bonus: items consumed continuously have higher real value
            shop_demand_bonus = 1.0 + min(town_drain.get(crop, 0), 4) * 0.20

            # Opponent saturation penalty: if opponent flooded this crop, penalize EV
            opp_penalty = (
                0.50
                if opp_supply.get(crop, 0) >= 18
                else (0.80 if opp_supply.get(crop, 0) >= 8 else 1.0)
            )

            # Early liquidity factor: when cash is constrained (<$2000),
            # prioritize instant cash infusion
            if state.money < 2000 and len(state.unlocked_quadrants) < 2:
                # First harvest cash burst
                first_yield_qty = (
                    6 if crop in {"WHEAT", "MELON"} else (4 if crop == "CARROT" else 2)
                )
                first_rev = (est_unit_price * first_yield_qty) - seed_cost
                liquidity_velocity = first_rev / max(1, maturity)
                ev_per_day = liquidity_velocity * opp_penalty
            elif crop == "STRAWBERRY":
                cycles = max(1, (horizon - 10) // 2 + 1) if horizon >= 10 else 1
                # Account for fertilizer doubling yield if livestock is active
                per_harvest = 3.5 if self._animal_count(state) > 0 else 2.0
                est_revenue = (est_unit_price * per_harvest * cycles) - seed_cost
                eff_maturity = max(maturity, min(horizon, 10 + (cycles - 1) * 2))
                ev_per_day = (est_revenue / max(1, eff_maturity)) * shop_demand_bonus * opp_penalty
            elif crop == "TOMATO":
                cycles = max(1, (horizon - 8) // 1 + 1) if horizon >= 8 else 1
                per_harvest = 3.0 if self._animal_count(state) > 0 else 1.0
                est_revenue = (est_unit_price * per_harvest * cycles) - seed_cost
                eff_maturity = max(maturity, min(horizon, 8 + (cycles - 1) * 1))
                ev_per_day = (est_revenue / max(1, eff_maturity)) * shop_demand_bonus * opp_penalty
            else:
                max_yield = 6 if crop in {"WHEAT", "MELON"} else 4
                est_revenue = (est_unit_price * max_yield) - seed_cost
                eff_maturity = maturity
                ev_per_day = (est_revenue / max(1, eff_maturity)) * shop_demand_bonus * opp_penalty

            scored.append((ev_per_day, crop))

        scored.sort(reverse=True)
        if not scored:
            return []

        allocated: list[tuple[str, int]] = []
        remaining_slots = empty_slots

        # Ensure wheat reserve for active animals
        if (self._animal_count(state) > 0 or state.day == 0) and state.shed.get("WHEAT", 0) < 4:
            wheat_reserved = min(remaining_slots, 4)
            allocated.append(("WHEAT", wheat_reserved))
            remaining_slots -= wheat_reserved

        if remaining_slots <= 0:
            return allocated

        # Focus primary slots on highest scored crop
        primary_crop = scored[0][1]
        allocated.append((primary_crop, remaining_slots))
        return allocated

    # ------------------------------------------------------------------
    # 2. Enhanced Tasks: Fertilizer Application to Regrowables
    # ------------------------------------------------------------------

    def _tasks(self, state: NormalizedState, goals: tuple[ProductionGoal, ...]) -> list[Task]:
        tasks = super()._tasks(state, goals)

        # Add FERTILIZE tasks for Strawberry and Tomato if fertilizer is in inventory/shed
        has_fert = state.shed.get("FERTILIZER", 0) > 0 or any(
            inv.get("FERTILIZER", 0) > 0 for inv in state.unit_inventories
        )
        if has_fert:
            for tile in state.tiles:
                if (
                    tile.kind == "PLANT"
                    and tile.crop in ("STRAWBERRY", "TOMATO")
                    and (
                        tile.fertilized_until_day is None or tile.fertilized_until_day <= state.day
                    )
                    and tile.fertilizer == 0
                ):
                    point = (tile.x, tile.y)
                    tasks.append(Task(4, point, ["FERTILIZE"], _has_fertilizer, ("tile", point)))

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

    # ------------------------------------------------------------------
    # 3. Market Orders: Quad 4 Unlock & Dynamic Price Sales
    # ------------------------------------------------------------------

    def _build_market_orders(
        self, state: NormalizedState, goals: tuple[ProductionGoal, ...], tasks: list[Task]
    ) -> list[list[Any]]:
        orders = super()._build_market_orders(state, goals, tasks)

        # Proactively expand to 3rd and 4th quadrant when capital allows
        if (
            state.day >= 4
            and len(state.unlocked_quadrants) < 4
            and len(orders) < self.v7_config.max_orders
            and not self._has_pending_chain(state)
            and not any(o[0] == "BUY_LAND" for o in orders)
        ):
            land_costs = [1000, 2000, 4000]
            quad_index = len(state.unlocked_quadrants) - 1
            if quad_index < len(land_costs):
                next_cost = land_costs[quad_index]
                if state.money >= next_cost + 400:
                    orders.append(["BUY_LAND"])

        return orders[: self.v7_config.max_orders]

    def _sales(
        self, state: NormalizedState, projected: dict[str, int] | None = None
    ) -> list[list[Any]]:
        orders: list[list[Any]] = []
        is_closing = self._closing(state)
        capacity_pressure = sum(state.shed.values()) >= (
            state.shed_capacity - self.v7_config.shed_safety_buffer
        )
        low_liquidity = state.money < self.v7_config.liquidity_cash_floor

        # Count regrowable crops
        regrowable_count = sum(
            1 for t in state.tiles if t.kind == "PLANT" and t.crop in ("STRAWBERRY", "TOMATO")
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
            elif item == "FERTILIZER" and not is_closing:
                if low_liquidity or regrowable_count == 0:
                    sellable = amount
                else:
                    fert_to_keep = min(2, regrowable_count, amount)
                    sellable = max(0, amount - fert_to_keep)
            else:
                sellable = amount

            if sellable <= 0:
                continue

            if (
                is_closing
                or capacity_pressure
                or low_liquidity
                or item == "MELON"
                or (item in {"MILK", "WOOL", "STRAWBERRY", "TOMATO"} and amount >= 2)
            ):
                orders.append(["SELL", item, sellable])
                continue

            values = marginal_sale_values(
                item,
                state.market_inventory.get(item, 10_000),
                sellable,
                opponent_buffer=self.v7_config.opponent_market_buffer,
            )
            base = state.prices.get(item, _CROP_BASE_PRICES.get(item, 25))
            units_to_sell = sum(1 for val in values if val >= base * 0.60)
            if units_to_sell > 0:
                orders.append(["SELL", item, units_to_sell])

        return orders
